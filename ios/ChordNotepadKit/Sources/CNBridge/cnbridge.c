// The Python half of ChordNotepadKit's plumbing: the interpreter's start, the
// _cnbridge extension module and the calls into the session handle. See
// include/cnbridge.h for the contract and docs/IOS.md for the threading rules.

#include "cn_python.h"
#include "cnbridge.h"

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// -- shared state ---------------------------------------------------------------
//
// Written by Swift (any thread), read by Python's threads: guarded by g_lock.
// The callbacks are copied out under the lock and called without it.

static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static CNEmitFn g_emit = NULL;
static void *g_emit_context = NULL;
static CNStoreCallbacks g_store;
static int g_has_store = 0;
static int g_initialized = 0;

static PyObject *StoreError = NULL;              // _cnbridge.StoreError
static PyObject *RenameUnsupportedError = NULL;  // _cnbridge.RenameUnsupportedError

void cn_free(void *pointer) {
    free(pointer);
}

static char *dup_cstring(const char *text) {
    size_t n = strlen(text);
    char *copy = malloc(n + 1);
    if (copy != NULL) {
        memcpy(copy, text, n + 1);
    }
    return copy;
}

static void set_error(char **error, const char *message) {
    if (error != NULL) {
        *error = dup_cstring(message);
    }
}

// A str as malloc'd UTF-8. Lone surrogates (which UTF-8 can't carry) become
// '?' instead of failing. Needs the GIL; NULL with a Python error set if even
// that fails.
static char *utf8_dup(PyObject *text, Py_ssize_t *out_len) {
    Py_ssize_t len = 0;
    const char *utf8 = PyUnicode_AsUTF8AndSize(text, &len);
    PyObject *encoded = NULL;
    if (utf8 == NULL) {
        PyErr_Clear();
        encoded = PyUnicode_AsEncodedString(text, "utf-8", "replace");
        if (encoded == NULL) {
            return NULL;
        }
        utf8 = PyBytes_AS_STRING(encoded);
        len = PyBytes_GET_SIZE(encoded);
    }
    char *copy = malloc((size_t)len + 1);
    if (copy == NULL) {
        Py_XDECREF(encoded);
        PyErr_NoMemory();
        return NULL;
    }
    memcpy(copy, utf8, (size_t)len);
    copy[len] = '\0';
    Py_XDECREF(encoded);
    if (out_len != NULL) {
        *out_len = len;
    }
    return copy;
}

// Clears the raised Python exception into `*error`: the formatted traceback,
// else str(exc). Needs the GIL.
static void take_python_error(char **error) {
    PyObject *exc = PyErr_GetRaisedException();
    if (exc == NULL) {
        set_error(error, "Python call failed without an exception");
        return;
    }
    PyObject *text = NULL;
    PyObject *traceback = PyImport_ImportModule("traceback");
    if (traceback != NULL) {
        PyObject *lines = PyObject_CallMethod(traceback, "format_exception", "O", exc);
        if (lines != NULL) {
            PyObject *empty = PyUnicode_FromString("");
            if (empty != NULL) {
                text = PyUnicode_Join(empty, lines);
                Py_DECREF(empty);
            }
            Py_DECREF(lines);
        }
        Py_DECREF(traceback);
    }
    if (text == NULL) {
        PyErr_Clear();
        text = PyObject_Str(exc);
    }
    char *message = text != NULL ? utf8_dup(text, NULL) : NULL;
    if (message == NULL) {
        PyErr_Clear();
        set_error(error, "Python call failed (the error couldn't be formatted)");
    } else if (error != NULL) {
        *error = message;
    } else {
        free(message);
    }
    Py_XDECREF(text);
    Py_DECREF(exc);
}

// -- the _cnbridge module ------------------------------------------------------------

static PyObject *raise_store_error(int32_t code, char *message) {
    PyObject *cls = code == CN_RENAME_UNSUPPORTED ? RenameUnsupportedError : StoreError;
    const char *text = message != NULL ? message : "The document store failed";
    // The message is the exception's only argument: callback_store shows str(exc).
    PyObject *value = PyUnicode_DecodeUTF8(text, (Py_ssize_t)strlen(text), "replace");
    if (value != NULL) {
        PyErr_SetObject(cls, value);
        Py_DECREF(value);
    }
    free(message);
    return NULL;
}

static int get_store(CNStoreCallbacks *out) {
    pthread_mutex_lock(&g_lock);
    int has = g_has_store;
    if (has) {
        *out = g_store;
    }
    pthread_mutex_unlock(&g_lock);
    if (!has) {
        PyErr_SetString(StoreError, "No document store is registered");
    }
    return has;
}

static int missing(const void *callback, const char *name) {
    if (callback == NULL) {
        PyErr_Format(StoreError, "The document store has no %s", name);
        return 1;
    }
    return 0;
}

static PyObject *bridge_emit(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *type_name;
    PyObject *json;
    if (!PyArg_ParseTuple(args, "UU:emit", &type_name, &json)) {
        return NULL;
    }
    Py_ssize_t type_len = 0;
    Py_ssize_t json_len = 0;
    char *type_utf8 = utf8_dup(type_name, &type_len);
    if (type_utf8 == NULL) {
        return NULL;
    }
    char *json_utf8 = utf8_dup(json, &json_len);
    if (json_utf8 == NULL) {
        free(type_utf8);
        return NULL;
    }
    pthread_mutex_lock(&g_lock);
    CNEmitFn emit = g_emit;
    void *context = g_emit_context;
    pthread_mutex_unlock(&g_lock);
    if (emit != NULL) {
        Py_BEGIN_ALLOW_THREADS
        emit(context, type_utf8, (size_t)type_len, json_utf8, (size_t)json_len);
        Py_END_ALLOW_THREADS
    }
    free(type_utf8);
    free(json_utf8);
    Py_RETURN_NONE;
}

static PyObject *store_read_bytes(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    if (!PyArg_ParseTuple(args, "s:store_read_bytes", &document_id)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.read_bytes, "read_bytes")) {
        return NULL;
    }
    uint8_t *data = NULL;
    size_t len = 0;
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.read_bytes(store.context, document_id, &data, &len, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        free(data);
        return raise_store_error(code, error);
    }
    free(error);
    if (data == NULL && len > 0) {
        PyErr_SetString(StoreError, "The document store returned no data");
        return NULL;
    }
    PyObject *result = PyBytes_FromStringAndSize(data != NULL ? (const char *)data : "",
                                                 (Py_ssize_t)len);
    free(data);
    return result;
}

static PyObject *store_write_bytes(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    Py_buffer data;
    if (!PyArg_ParseTuple(args, "sy*:store_write_bytes", &document_id, &data)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.write_bytes, "write_bytes")) {
        PyBuffer_Release(&data);
        return NULL;
    }
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.write_bytes(store.context, document_id, (const uint8_t *)data.buf,
                             (size_t)data.len, &error);
    Py_END_ALLOW_THREADS
    PyBuffer_Release(&data);
    if (code != CN_OK) {
        return raise_store_error(code, error);
    }
    free(error);
    Py_RETURN_NONE;
}

static PyObject *store_copy_from_file(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    const char *path;
    if (!PyArg_ParseTuple(args, "ss:store_copy_from_file", &document_id, &path)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.copy_from_file, "copy_from_file")) {
        return NULL;
    }
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.copy_from_file(store.context, document_id, path, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        return raise_store_error(code, error);
    }
    free(error);
    Py_RETURN_NONE;
}

static PyObject *store_is_available(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    if (!PyArg_ParseTuple(args, "s:store_is_available", &document_id)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.is_available, "is_available")) {
        return NULL;
    }
    int32_t available = 0;
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.is_available(store.context, document_id, &available, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        return raise_store_error(code, error);
    }
    free(error);
    return PyBool_FromLong(available != 0);
}

// A malloc'd UTF-8 string from a callback as a str (or None for NULL when
// `none_ok`), freeing it.
static PyObject *take_string(char *text, int none_ok) {
    if (text == NULL) {
        if (none_ok) {
            Py_RETURN_NONE;
        }
        PyErr_SetString(StoreError, "The document store returned no text");
        return NULL;
    }
    PyObject *result = PyUnicode_DecodeUTF8(text, (Py_ssize_t)strlen(text), "replace");
    free(text);
    return result;
}

static PyObject *store_recent(PyObject *self, PyObject *args) {
    (void)self;
    if (!PyArg_ParseTuple(args, ":store_recent")) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.recent, "recent")) {
        return NULL;
    }
    char *json = NULL;
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.recent(store.context, &json, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        free(json);
        return raise_store_error(code, error);
    }
    free(error);
    return take_string(json, 0);
}

static PyObject *store_add_recent(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    const char *display_name;
    const char *location;
    if (!PyArg_ParseTuple(args, "sss:store_add_recent", &document_id, &display_name, &location)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.add_recent, "add_recent")) {
        return NULL;
    }
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.add_recent(store.context, document_id, display_name, location, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        return raise_store_error(code, error);
    }
    free(error);
    Py_RETURN_NONE;
}

static PyObject *store_set_max_recent(PyObject *self, PyObject *args) {
    (void)self;
    long long count;
    if (!PyArg_ParseTuple(args, "L:store_set_max_recent", &count)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.set_max_recent, "set_max_recent")) {
        return NULL;
    }
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.set_max_recent(store.context, (int64_t)count, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        return raise_store_error(code, error);
    }
    free(error);
    Py_RETURN_NONE;
}

static PyObject *store_describe(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    if (!PyArg_ParseTuple(args, "s:store_describe", &document_id)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.describe, "describe")) {
        return NULL;
    }
    char *json = NULL;
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.describe(store.context, document_id, &json, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        free(json);
        return raise_store_error(code, error);
    }
    free(error);
    return take_string(json, 1);
}

static PyObject *store_rename(PyObject *self, PyObject *args) {
    (void)self;
    const char *document_id;
    const char *display_name;
    if (!PyArg_ParseTuple(args, "ss:store_rename", &document_id, &display_name)) {
        return NULL;
    }
    CNStoreCallbacks store;
    if (!get_store(&store) || missing((const void *)store.rename, "rename")) {
        return NULL;
    }
    char *json = NULL;
    char *error = NULL;
    int32_t code;
    Py_BEGIN_ALLOW_THREADS
    code = store.rename(store.context, document_id, display_name, &json, &error);
    Py_END_ALLOW_THREADS
    if (code != CN_OK) {
        free(json);
        return raise_store_error(code, error);
    }
    free(error);
    return take_string(json, 0);
}

static PyMethodDef bridge_methods[] = {
    {"emit", bridge_emit, METH_VARARGS,
     "emit(type_name, json): hand one session output to Swift."},
    {"store_read_bytes", store_read_bytes, METH_VARARGS, "store_read_bytes(id) -> bytes"},
    {"store_write_bytes", store_write_bytes, METH_VARARGS, "store_write_bytes(id, data)"},
    {"store_copy_from_file", store_copy_from_file, METH_VARARGS,
     "store_copy_from_file(id, path)"},
    {"store_is_available", store_is_available, METH_VARARGS, "store_is_available(id) -> bool"},
    {"store_recent", store_recent, METH_VARARGS, "store_recent() -> str (a JSON array of refs)"},
    {"store_add_recent", store_add_recent, METH_VARARGS,
     "store_add_recent(id, display_name, location)"},
    {"store_set_max_recent", store_set_max_recent, METH_VARARGS, "store_set_max_recent(count)"},
    {"store_describe", store_describe, METH_VARARGS,
     "store_describe(id) -> str | None (the ref as JSON)"},
    {"store_rename", store_rename, METH_VARARGS,
     "store_rename(id, display_name) -> str (the new ref as JSON)"},
    {NULL, NULL, 0, NULL},
};

static int bridge_exec(PyObject *module) {
    StoreError = PyErr_NewExceptionWithDoc(
        "_cnbridge.StoreError",
        "A document store call failed; the message is user-facing.", NULL, NULL);
    if (StoreError == NULL || PyModule_AddObjectRef(module, "StoreError", StoreError) < 0) {
        return -1;
    }
    RenameUnsupportedError = PyErr_NewExceptionWithDoc(
        "_cnbridge.RenameUnsupportedError",
        "The storage can't rename this document (the UI offers Save As).", StoreError, NULL);
    if (RenameUnsupportedError == NULL ||
        PyModule_AddObjectRef(module, "RenameUnsupportedError", RenameUnsupportedError) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot bridge_slots[] = {
    {Py_mod_exec, (void *)bridge_exec},
    {0, NULL},
};

static struct PyModuleDef bridge_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_cnbridge",
    .m_doc = "ChordNotepadKit's native bridge: events and document store callbacks to Swift.",
    .m_size = 0,
    .m_methods = bridge_methods,
    .m_slots = bridge_slots,
};

static PyObject *init_cnbridge(void) {
    return PyModuleDef_Init(&bridge_module);
}

// -- the interpreter -------------------------------------------------------------------

static int32_t status_error(PyStatus status, char **error) {
    char message[512];
    snprintf(message, sizeof message, "Python didn't start: %s%s%s",
             status.func != NULL ? status.func : "",
             status.func != NULL ? ": " : "",
             status.err_msg != NULL ? status.err_msg : (PyStatus_IsExit(status) ? "exit" : "error"));
    set_error(error, message);
    return CN_ERROR;
}

int32_t cn_runtime_initialize(const CNRuntimeOptions *options, char **error) {
    if (g_initialized || Py_IsInitialized()) {
        set_error(error, "Python is already running (one interpreter per process)");
        return CN_ERROR;
    }
    PyStatus status;
    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) {
        return status_error(status, error);
    }
    if (PyImport_AppendInittab("_cnbridge", init_cnbridge) != 0) {
        set_error(error, "Couldn't register the _cnbridge module");
        return CN_ERROR;
    }

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.install_signal_handlers = 0;
    config.write_bytecode = options->write_bytecode != 0;
#if defined(__APPLE__)
    config.use_system_logger = options->use_system_logger != 0;
#endif
    if (options->home != NULL) {
        status = PyConfig_SetBytesString(&config, &config.home, options->home);
        if (PyStatus_Exception(status)) {
            PyConfig_Clear(&config);
            return status_error(status, error);
        }
    }
    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        return status_error(status, error);
    }

    // CPython computed the stdlib's place; our folders go in front of it.
    PyObject *path = PySys_GetObject("path");  // borrowed
    int32_t result = CN_OK;
    if (path == NULL || !PyList_Check(path)) {
        set_error(error, "sys.path is missing");
        result = CN_ERROR;
    } else {
        for (size_t i = 0; i < options->path_count && result == CN_OK; i++) {
            PyObject *entry = PyUnicode_DecodeFSDefault(options->paths[i]);
            if (entry == NULL || PyList_Insert(path, (Py_ssize_t)i, entry) < 0) {
                take_python_error(error);
                result = CN_ERROR;
            }
            Py_XDECREF(entry);
        }
    }
    g_initialized = 1;
    // From here on every call takes the GIL with PyGILState_Ensure.
    (void)PyEval_SaveThread();
    return result;
}

int32_t cn_runtime_is_initialized(void) {
    return g_initialized;
}

void cn_set_event_sink(CNEmitFn emit, void *context) {
    pthread_mutex_lock(&g_lock);
    g_emit = emit;
    g_emit_context = context;
    pthread_mutex_unlock(&g_lock);
}

void cn_set_store(const CNStoreCallbacks *callbacks) {
    pthread_mutex_lock(&g_lock);
    if (callbacks != NULL) {
        g_store = *callbacks;
        g_has_store = 1;
    } else {
        memset(&g_store, 0, sizeof g_store);
        g_has_store = 0;
    }
    pthread_mutex_unlock(&g_lock);
}

// -- calls into Python -------------------------------------------------------------------

static int require_runtime(char **error) {
    if (!g_initialized) {
        set_error(error, "Python isn't running");
        return 0;
    }
    return 1;
}

// module.function, a new reference, or NULL with a Python error set.
static PyObject *lookup(const char *module_name, const char *function) {
    PyObject *module = PyImport_ImportModule(module_name);
    if (module == NULL) {
        return NULL;
    }
    PyObject *callable = PyObject_GetAttrString(module, function);
    Py_DECREF(module);
    return callable;
}

int32_t cn_call_strings(const char *module, const char *function,
                        const char *const *args, size_t arg_count,
                        char **out_result, char **error) {
    if (!require_runtime(error)) {
        return CN_ERROR;
    }
    if (out_result != NULL) {
        *out_result = NULL;
    }
    int32_t code = CN_ERROR;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *callable = lookup(module, function);
    PyObject *tuple = callable != NULL ? PyTuple_New((Py_ssize_t)arg_count) : NULL;
    PyObject *result = NULL;
    if (tuple != NULL) {
        int ok = 1;
        for (size_t i = 0; i < arg_count && ok; i++) {
            PyObject *arg = PyUnicode_FromString(args[i]);
            if (arg == NULL) {
                ok = 0;
            } else {
                PyTuple_SET_ITEM(tuple, (Py_ssize_t)i, arg);  // steals
            }
        }
        if (ok) {
            result = PyObject_Call(callable, tuple, NULL);
        }
    }
    if (result != NULL) {
        if (result == Py_None) {
            code = CN_OK;
        } else {
            PyObject *text = PyObject_Str(result);
            char *copy = text != NULL ? utf8_dup(text, NULL) : NULL;
            Py_XDECREF(text);
            if (copy != NULL) {
                code = CN_OK;
                if (out_result != NULL) {
                    *out_result = copy;
                } else {
                    free(copy);
                }
            }
        }
    }
    if (code != CN_OK) {
        take_python_error(error);
    }
    Py_XDECREF(result);
    Py_XDECREF(tuple);
    Py_XDECREF(callable);
    PyGILState_Release(gil);
    return code;
}

int32_t cn_start_handle(const char *module, const char *function, const char *options_json,
                        void **out_handle, char **error) {
    *out_handle = NULL;
    if (!require_runtime(error)) {
        return CN_ERROR;
    }
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *callable = lookup(module, function);
    PyObject *handle = callable != NULL
        ? PyObject_CallFunction(callable, "s", options_json) : NULL;
    int32_t code = CN_OK;
    if (handle == NULL) {
        take_python_error(error);
        code = CN_ERROR;
    } else {
        *out_handle = handle;  // the new reference, released by cn_handle_release
    }
    Py_XDECREF(callable);
    PyGILState_Release(gil);
    return code;
}

int32_t cn_handle_submit(void *handle, const char *command, const char *args_json,
                         char **error) {
    if (!require_runtime(error)) {
        return CN_ERROR;
    }
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *result = PyObject_CallMethod((PyObject *)handle, "submit", "ss", command, args_json);
    int32_t code = CN_OK;
    if (result == NULL) {
        take_python_error(error);
        code = CN_ERROR;
    }
    Py_XDECREF(result);
    PyGILState_Release(gil);
    return code;
}

int32_t cn_handle_chord_sheet_buffer(void *handle, double height, uint8_t **out_data,
                                     size_t *out_len, int32_t *out_is_none, char **error) {
    *out_data = NULL;
    *out_len = 0;
    *out_is_none = 0;
    if (!require_runtime(error)) {
        return CN_ERROR;
    }
    PyGILState_STATE gil = PyGILState_Ensure();
    int32_t code = CN_OK;
    PyObject *result = PyObject_CallMethod((PyObject *)handle, "chord_sheet_buffer", "d", height);
    if (result == NULL) {
        take_python_error(error);
        code = CN_ERROR;
    } else if (result == Py_None) {
        *out_is_none = 1;
    } else {
        Py_buffer view;
        if (PyObject_GetBuffer(result, &view, PyBUF_SIMPLE) < 0) {
            take_python_error(error);
            code = CN_ERROR;
        } else {
            uint8_t *copy = malloc(view.len > 0 ? (size_t)view.len : 1);
            if (copy == NULL) {
                set_error(error, "Out of memory copying the chord sheet buffer");
                code = CN_ERROR;
            } else {
                memcpy(copy, view.buf, (size_t)view.len);
                *out_data = copy;
                *out_len = (size_t)view.len;
            }
            PyBuffer_Release(&view);
        }
    }
    Py_XDECREF(result);
    PyGILState_Release(gil);
    return code;
}

int32_t cn_handle_shutdown(void *handle, char **error) {
    if (!require_runtime(error)) {
        return CN_ERROR;
    }
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *result = PyObject_CallMethod((PyObject *)handle, "shutdown", NULL);
    int32_t code = CN_OK;
    if (result == NULL) {
        take_python_error(error);
        code = CN_ERROR;
    }
    Py_XDECREF(result);
    PyGILState_Release(gil);
    return code;
}

void cn_handle_release(void *handle) {
    if (handle == NULL || !g_initialized) {
        return;
    }
    PyGILState_STATE gil = PyGILState_Ensure();
    Py_DECREF((PyObject *)handle);
    PyGILState_Release(gil);
}
