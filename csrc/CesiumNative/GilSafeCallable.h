#pragma once

#include <pybind11/pybind11.h>

#include <utility>

namespace py = pybind11;

// Owns a Python callable captured into a cesium-native continuation.
//
// cesium-native destroys a continuation on whichever thread settles the
// future, usually a worker thread that does not hold the GIL. A plain
// py::function captured by value would then Py_DECREF without the GIL, which
// corrupts the interpreter state and crashes intermittently. This wrapper
// takes the GIL for every reference-count change it makes (copy and
// destruction); a move transfers the reference and touches no count.
//
// The caller must hold the GIL when invoking operator().
class GilSafeCallable {
public:
  explicit GilSafeCallable(py::object callable) : obj_(std::move(callable)) {}

  GilSafeCallable(const GilSafeCallable& other) {
    py::gil_scoped_acquire gil;
    obj_ = other.obj_;
  }

  GilSafeCallable(GilSafeCallable&& other) noexcept = default;
  GilSafeCallable& operator=(const GilSafeCallable&) = delete;
  GilSafeCallable& operator=(GilSafeCallable&&) = delete;

  ~GilSafeCallable() {
    if (obj_.ptr() == nullptr) {
      return;
    }
    if (!Py_IsInitialized()) {
      // interpreter gone: leak the reference rather than touch it
      obj_.release();
      return;
    }
    py::gil_scoped_acquire gil;
    obj_ = py::object();
  }

  template <typename... Args> py::object operator()(Args&&... args) const {
    return obj_(std::forward<Args>(args)...);
  }

private:
  py::object obj_;
};
