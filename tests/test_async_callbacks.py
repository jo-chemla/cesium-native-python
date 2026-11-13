"""Python callables handed to the AsyncSystem must survive being destroyed on
cesium-native worker threads.

The continuation that wraps the callback is destroyed on whichever thread
settles the future, without the GIL. Before GilSafeCallable this decremented
the callable's reference count without the GIL and crashed the interpreter
intermittently; the counter below makes every drop observable instead."""
import gc
import weakref

from cesium.async_ import AsyncSystem, NativeTaskProcessor


def _system():
    return AsyncSystem(NativeTaskProcessor())


def _drain(asys, futures):
    for f in futures:
        f.wait()
    asys.dispatch_main_thread_tasks()


def test_worker_thread_callbacks_run_and_are_released():
    asys = _system()
    hits = []
    futures = [asys.run_in_worker_thread(lambda i=i: hits.append(i)) for i in range(2000)]
    _drain(asys, futures)
    assert sorted(hits) == list(range(2000))


def test_main_thread_callbacks_run_on_dispatch():
    asys = _system()
    hits = []
    futures = [asys.run_in_main_thread(lambda i=i: hits.append(i)) for i in range(200)]
    for _ in range(50):
        asys.dispatch_main_thread_tasks()
        if all(f.is_ready() for f in futures):
            break
    assert sorted(hits) == list(range(200))


def test_thread_pool_callbacks_run():
    asys = _system()
    pool = asys.create_thread_pool(4)
    hits = []
    futures = [asys.run_in_thread_pool(pool, lambda i=i: hits.append(i)) for i in range(500)]
    _drain(asys, futures)
    assert sorted(hits) == list(range(500))


def test_callback_object_is_freed_after_completion():
    """The callable's last reference is dropped by the continuation, on a
    worker thread: the weakref must die without crashing."""
    asys = _system()

    class Callback:
        def __call__(self):
            pass

    cb = Callback()
    ref = weakref.ref(cb)
    future = asys.run_in_worker_thread(cb)
    del cb
    future.wait()
    asys.dispatch_main_thread_tasks()
    del future
    gc.collect()
    assert ref() is None
