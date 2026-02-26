# Makefile Walkthrough

I have created a `Makefile` to automate common tasks for the FastFootSatıs project.

## New Commands

The following commands are now available:

| Command | Description |
| :--- | :--- |
| `make help` | Shows all available commands. |
| `make run` | Runs the web server locally using the virtual environment. |
| `make install` | Installs dependencies from `requirements.txt`. |
| `make deploy` | Deploys the code to the remote server and restarts the service. |
| `make status` | Checks the remote service status. |
| `make logs` | Follows the remote service logs. |
| `make ssh` | Starts an SSH session to the remote server. |

## Verification Results

### `make help` Execution
I verified that `make help` correctly lists all the commands.

```bash
Available commands:
  make run      - Run the web server locally
  make install  - Install dependencies from requirements.txt
  make deploy   - Sync files to remote server and restart service
  make status   - Check status of remote service
  make logs     - View remote service logs
  make ssh      - SSH into the remote server
```

### Local Setup
The `Makefile` uses the `.venv` directory for Python execution, ensuring consistency with your existing environment.
