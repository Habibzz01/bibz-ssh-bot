import os
import json
import asyncio
import logging
import asyncssh
from typing import Optional

logger = logging.getLogger(__name__)

SERVERS_FILE = "servers.json"

_server_registry = {}


def load_servers():
    global _server_registry
    if os.path.exists(SERVERS_FILE):
        try:
            with open(SERVERS_FILE) as f:
                _server_registry = json.load(f)
            logger.info(f"Loaded {len(_server_registry)} servers from {SERVERS_FILE}")
        except Exception as e:
            logger.error(f"Failed to load servers: {e}")
            _server_registry = {}


def save_servers():
    try:
        with open(SERVERS_FILE, "w") as f:
            json.dump(_server_registry, f, indent=2)
        logger.info(f"Saved {len(_server_registry)} servers to {SERVERS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save servers: {e}")


def add_server(name: str, host: str, user: str, port: int = 22, key: str = "", password: str = "", local: bool = False) -> bool:
    if name in _server_registry:
        return False
    _server_registry[name] = {
        "host": host,
        "user": user,
        "port": port,
        "key": key,
        "password": password,
        "local": local,
    }
    save_servers()
    return True


def remove_server(name: str) -> bool:
    if name not in _server_registry:
        return False
    del _server_registry[name]
    save_servers()
    return True


def list_servers() -> list:
    return list(_server_registry.keys())


def get_server(name: str) -> Optional[dict]:
    return _server_registry.get(name)


async def ssh_exec(server_name: str, command: str, timeout: int = 60) -> tuple:
    info = get_server(server_name)
    if not info:
        return (False, "Server not found")

    if info.get("local"):
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode() if stdout else ""
            err = stderr.decode() if stderr else ""
            if proc.returncode == 0:
                return (True, out)
            else:
                return (False, err or out)
        except asyncio.TimeoutError:
            return (False, "Command timed out")
        except Exception as e:
            return (False, f"Error: {e}")

    try:
        kwargs = {
            "host": info["host"],
            "username": info["user"],
            "port": info.get("port", 22),
            "known_hosts": None,
        }
        if info.get("key"):
            kwargs["client_keys"] = [info["key"]]
        if info.get("password"):
            kwargs["password"] = info["password"]

        async with asyncssh.connect(**kwargs) as conn:
            result = await conn.run(command, timeout=timeout)
            if result.returncode == 0:
                return (True, result.stdout)
            else:
                return (False, result.stderr or result.stdout)
    except asyncssh.Error as e:
        return (False, f"SSH Error: {e}")
    except asyncio.TimeoutError:
        return (False, "Command timed out")
    except Exception as e:
        return (False, f"Error: {e}")


async def ssh_upload(server_name: str, local_path: str, remote_path: str) -> tuple:
    info = get_server(server_name)
    if not info:
        return (False, "Server not found")

    try:
        kwargs = {
            "host": info["host"],
            "username": info["user"],
            "port": info.get("port", 22),
            "known_hosts": None,
        }
        if info.get("key"):
            kwargs["client_keys"] = [info["key"]]
        if info.get("password"):
            kwargs["password"] = info["password"]

        async with asyncssh.connect(**kwargs) as conn:
            async with asyncssh.scp((local_path, remote_path), connect_kwargs=kwargs) as scp:
                pass
            return (True, "File uploaded")
    except Exception as e:
        return (False, f"Upload failed: {e}")
