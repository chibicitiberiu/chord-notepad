// CPython's headers: the iOS Python.xcframework ships them as a framework
// (<Python/Python.h>); Linux and a Mac's Homebrew Python as <Python.h>.
#ifndef CN_CPYTHON_SHIM_H
#define CN_CPYTHON_SHIM_H

#define PY_SSIZE_T_CLEAN
#if __has_include(<Python/Python.h>)
#include <Python/Python.h>
#else
#include <Python.h>
#endif

#endif
