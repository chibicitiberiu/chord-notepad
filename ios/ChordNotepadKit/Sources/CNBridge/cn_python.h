// A private copy of ../CPython/shim.h: C targets include headers by path, not through the module map.
// CPython's headers: the iOS Python.xcframework ships them as a framework
// (<Python/Python.h>); Linux and a Mac host's Python (pkg-config) as
// <Python.h>. A Mac host never takes the framework form: /Library/Frameworks
// is on clang's default search path and its Python.framework may be another
// version than the one pkg-config links.
#ifndef CN_PYTHON_H
#define CN_PYTHON_H

#define PY_SSIZE_T_CLEAN
#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif
#if defined(__APPLE__) && TARGET_OS_IOS
#include <Python/Python.h>
#else
#include <Python.h>
#endif

#endif
