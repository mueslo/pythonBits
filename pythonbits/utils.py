from concurrent.futures import ThreadPoolExecutor

def threadmap(f, it, n_threads=10):
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        jobs = [executor.submit(f, i) for i in it]
        for j in jobs:
            yield j.result()