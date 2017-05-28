# Cyber Safe

A final project for the Gvahim program. This project offers a safe-like structure of servers for clients to safely upload and download files.
The program is based on different server points, all are HTTP servers:
A frontend server providing services to clients, such as file list and file download.
Multiple block device servers for the frontend to access and store the files and data in forms of blocks.

The program works the following way:
The client (browser) sends a request to the frontend.
The frontend reads needed blocks from the safe devices.
The frontend writes updated blocks to safe devices if needed.
The frontend returns response to client with wanted file/data.

Every server uses an AES algorithm of encryption on the contents it reads and writes.
In addition, for every file uploaded to the system, it's data is encrypted in AES using unique user-provided key.

The data of the files is split between all safe block devices using a bit-splitting algorithm, in such way that it can only be accessed by reading from all the devices.


## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

In order to run the project there are some requirments:
```
1) Download and install Python 2.7 (https://www.python.org/download/releases/2.7/)
2) Download this repository and extract the zip on every computer you wish to place a server.
3) Download and install the latest version of Google Chrome (https://www.google.com/chrome/browser/desktop/index.html)
5) Change the address and port in all block device configuration files to the ip of the matching computer.
6) In the frontend configuration file, make sure every block device gets an entry with the matching ip and port.

```

### Execution

To execute the project open Command Prompt (or Terminal on Linux):
Reach the parent folder of this project:
```
cd [location of cyber-safe]
```
Running frontend:
```
python -m frontend [args]
```
Running a block device:
```
python -m block_device [args]


### Arguments

All arguments are optional for every server, and can be viewed via providing -h or --help arguments.


### Graphical Interface

There is no graphical interface as part of the main program.
In order too enter the GUI in your Chrome browser.
type:
```
(frontend ip):(frontend port)
```
This will open the main page where you will be able to proceed as a client according to simple operations.


## Authors

* **Ron Kantorovich** - *Initial work* - [My Profile](https://github.com/TheClownFromDowntown)


## Acknowledgments

* Thanks to Alon and Sarit for all their support and great teaching!
* This project uses the pyaes module implemented by another Git user for simple AES encryption in Python: (https://github.com/ricmoo/pyaes)