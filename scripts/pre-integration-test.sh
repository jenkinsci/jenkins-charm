#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# [2022-09-29] Need to install Python 3.8 because that is what the tests run on and 18.04
sudo apt install python3.8
sudo update-alternatives --install /usr/local/bin/python python3 /usr/bin/python3.8 100
sudo update-alternatives --set python3 /usr/bin/python3.8
sudo update-alternatives --install /usr/local/bin/python python /usr/bin/python3.8 100
sudo update-alternatives --set python /usr/bin/python3.8