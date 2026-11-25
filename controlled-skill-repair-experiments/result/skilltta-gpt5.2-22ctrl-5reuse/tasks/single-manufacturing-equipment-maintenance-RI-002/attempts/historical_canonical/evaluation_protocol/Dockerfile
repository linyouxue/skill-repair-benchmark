FROM skilltta-controlled55-prebuild:d7fb1748899db45b
COPY verifier-wheelhouse-v2 /opt/skilltta-verifier-wheels-v2
RUN python3 -m venv /opt/skilltta-verifier-v2 && /opt/skilltta-verifier-v2/bin/python -m pip install --no-index --find-links /opt/skilltta-verifier-wheels-v2 pytest==8.4.1 pytest-json-ctrf==0.3.5 pandas==2.3.3
