# Betfair

## Setup Instructions

### Configuration:
In appsettings.json change:
- Filepath for betfairmarket.sqlite
- Filepath for betfair.pfx cert 

### Dependencies:
Make sure you have .Net 8.0 installed
Run dotnet restore

### Database:
Click + in the Database panel
Select SQLite.
In the configuration panel:
File: Browse to the SQLite database file: betfairmarket.sqlite
Driver: Rider will auto-detect the required SQLite driver (downloaded if needed and test the connection)

### To make it runnable:

