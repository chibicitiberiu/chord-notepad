// A private copy of ../CPython/shim.h: C targets include headers by path, not through the module map.
// CPython's headers: the iOS Python.xcframework ships them as a framework
// (<Python/Python.h>); Linux and a Mac's Homebrew Python as <Python.h>.
#ifndef CN_PYTHON_H
#define CN_PYTHON_H

#define PY_SSIZE_T_CLEAN
#if __has_include(<Python/Python.h>)
#include <Python/Python.h>
#else
#include <Python.h>
#endif

#endif
