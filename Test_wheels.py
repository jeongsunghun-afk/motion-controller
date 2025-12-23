# test_fitlet.py

import numpy as np
import scipy
from scipy import linalg
import requests
import plotly

def test_numpy():
    a = np.array([1, 2, 3])
    b = np.array([4, 5, 6])
    c = a + b
    print("NumPy test passed:", c)

def test_scipy():
    mat = np.array([[1, 2], [3, 4]])
    inv = linalg.inv(mat)
    print("SciPy test passed: inverse computed\n", inv)

def test_requests():
    response = requests.models.PreparedRequest()
    response.prepare_url("https://example.com", None)
    print("Requests test passed:", response.url)

if __name__ == "__main__":
    test_numpy()
    test_scipy()
    test_requests()
