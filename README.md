# siege-spider-client
Local Windows client for siege spider

# Setup

## Python Virtual Environment
```
poetry install
```

```
poetry shell
```

*Note - sometimes `poetry shell` doesn't work, if that's the case just run:*
```
source .venv/bin/activate
```

# Building

## Match Client 

```shell
chmod +x build_match_client.sh
```

```shell
./build_match_client.sh
```

*Note - if you build the client on a non-Windows platform, pyinstaller will automatically use that platforms executable binary format so the executable will not be cross-compatible to Windows unless you build on Windows.*
