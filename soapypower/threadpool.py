import os, queue, concurrent.futures


class ThreadPoolExecutor(concurrent.futures.ThreadPoolExecutor):
    """ThreadPoolExecutor which allows setting max. work queue size"""
    def __init__(self, max_workers=0, thread_name_prefix='', max_queue_size=0):
        super().__init__(max_workers or os.cpu_count() or 1, thread_name_prefix)
        self.max_queue_size = max_queue_size or self._max_workers * 10
        if self.max_queue_size > 0:
            self._work_queue = queue.Queue(self.max_queue_size)
        self.max_queue_size_reached = 0

    def submit(self, fn, *args, **kwargs):
        """Submits a callable to be executed with the given arguments.

        Count maximum reached work queue size in ThreadPoolExecutor.max_queue_size_reached.
        """
        future = super().submit(fn, *args, **kwargs)
        work_queue_size = self._work_queue.qsize()
        if work_queue_size > self.max_queue_size_reached:
            self.max_queue_size_reached = work_queue_size
        return future
