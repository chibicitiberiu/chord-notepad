// The C side of the Swift <-> Python bridge (docs/IOS.md, "Bridge contract").
//
// Every Python C API call is in cnbridge.c; Swift only sees this header. The
// calls below take the GIL themselves (PyGILState_Ensure/Release), so Swift may
// make them from its bridge thread without knowing about Python's thread
// states. Swift makes them from one thread only, never the main thread.
//
// Memory: every `char **error` / `char **out_*` / `uint8_t **out_data` the C
// side fills is malloc'd and owned by the caller (free it with cn_free). In
// the other direction, the store callbacks fill theirs with malloc'd memory
// and the C side frees it.

#ifndef CNBRIDGE_H
#define CNBRIDGE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/// Result codes of the cn_* calls and of the store callbacks.
enum {
    CN_OK = 0,
    /// Failed; `*error` holds a message (a store callback's is shown to the user).
    CN_ERROR = 1,
    /// Store `rename` only: the storage can't rename this document
    /// (Python raises RenameNotSupported, the UI offers Save As).
    CN_RENAME_UNSUPPORTED = 2,
};

/// How to start the interpreter.
typedef struct CNRuntimeOptions {
    /// PyConfig.home (the stdlib's prefix), or NULL for CPython's own search.
    const char *home;
    /// Folders put at the front of sys.path, in this order.
    const char *const *paths;
    size_t path_count;
    /// Write __pycache__ files (off for a read-only app bundle).
    int32_t write_bytecode;
    /// Send stdout/stderr to the system log (PyConfig.use_system_logger,
    /// Apple builds only; ignored elsewhere).
    int32_t use_system_logger;
} CNRuntimeOptions;

/// The session's output, one call per state or event, on Python's
/// `python-session` thread (the GIL is released during the call). Must return
/// quickly and never wait for the bridge thread.
typedef void (*CNEmitFn)(void *context, const char *type_name, size_t type_len,
                         const char *json, size_t json_len);

/// The documents Python reads and writes (Python's callbacks object, see
/// core/chordnotepad/session/callback_store.py). Called on the session thread,
/// and `write_bytes`/`copy_from_file` also on export worker threads: every one
/// must be safe on any thread. The GIL is released while they run, so they may
/// block on file I/O, but they must never wait for the bridge thread.
/// Each returns CN_OK, or CN_ERROR (or CN_RENAME_UNSUPPORTED) with a
/// malloc'd, user-facing UTF-8 message in `*error`.
typedef struct CNStoreCallbacks {
    void *context;
    /// The document's bytes, malloc'd into `*out_data` (NULL allowed when 0 long).
    int32_t (*read_bytes)(void *context, const char *document_id,
                          uint8_t **out_data, size_t *out_len, char **error);
    int32_t (*write_bytes)(void *context, const char *document_id,
                           const uint8_t *data, size_t len, char **error);
    int32_t (*copy_from_file)(void *context, const char *document_id,
                              const char *path, char **error);
    int32_t (*is_available)(void *context, const char *document_id,
                            int32_t *out_available, char **error);
    /// A JSON array of {"id", "display_name", "location"}, malloc'd.
    int32_t (*recent)(void *context, char **out_json, char **error);
    int32_t (*add_recent)(void *context, const char *document_id,
                          const char *display_name, const char *location, char **error);
    int32_t (*set_max_recent)(void *context, int64_t count, char **error);
    /// The ref as JSON, malloc'd, or NULL when unreachable.
    int32_t (*describe)(void *context, const char *document_id,
                        char **out_json, char **error);
    /// The renamed document's ref as JSON, malloc'd.
    int32_t (*rename)(void *context, const char *document_id,
                      const char *display_name, char **out_json, char **error);
} CNStoreCallbacks;

/// Start the interpreter (once per process; a second call fails). Registers
/// the _cnbridge module first, and releases the GIL before returning, so the
/// calls below can take it from any thread.
int32_t cn_runtime_initialize(const CNRuntimeOptions *options, char **error);

/// Whether cn_runtime_initialize succeeded.
int32_t cn_runtime_is_initialized(void);

/// Where _cnbridge.emit sends events (NULL drops them).
void cn_set_event_sink(CNEmitFn emit, void *context);

/// The store _cnbridge's store_* functions call (copied; NULL clears it).
void cn_set_store(const CNStoreCallbacks *callbacks);

/// `module.function(*string_args)`; `*out_result` is its str() (NULL for
/// None). For the Swift tests and small queries.
int32_t cn_call_strings(const char *module, const char *function,
                        const char *const *args, size_t arg_count,
                        char **out_result, char **error);

/// `module.function(options_json)`, keeping the returned object (the session
/// handle) in `*out_handle` as a new reference.
int32_t cn_start_handle(const char *module, const char *function, const char *options_json,
                        void **out_handle, char **error);

/// `handle.submit(command, args_json)`.
int32_t cn_handle_submit(void *handle, const char *command, const char *args_json,
                         char **error);

/// `handle.chord_sheet_buffer(height)`: the bytes malloc'd into `*out_data`, or
/// `*out_is_none` = 1 when Python returned None.
int32_t cn_handle_chord_sheet_buffer(void *handle, double height, uint8_t **out_data,
                                     size_t *out_len, int32_t *out_is_none, char **error);

/// `handle.shutdown()`.
int32_t cn_handle_shutdown(void *handle, char **error);

/// Drop the reference cn_start_handle returned.
void cn_handle_release(void *handle);

/// free() for what the cn_* calls returned.
void cn_free(void *pointer);

#ifdef __cplusplus
}
#endif

#endif
