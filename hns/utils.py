"""
Misc util functionality for HNS.
"""

import time
from contextlib import contextmanager


@contextmanager
def timeit(logger, what):
    start = time.time()
    yield
    duration = time.time() - start
    logger.debug("%s: took %f secs", what, duration)


def debug_image(image, title="Debug image", cmap="gray"):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 10))
    plt.title(title)
    plt.imshow(image, cmap=cmap)
    plt.show()
