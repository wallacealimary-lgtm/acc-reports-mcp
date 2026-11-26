"""
Starts the MCP server. This is the file Claude runs (see README, step 6).
Running it by path puts this folder on Python's import path, so no
package install is needed.
"""
from acc_reports_mcp.server import main

if __name__ == "__main__":
    main()
