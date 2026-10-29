@echo off
rem Midway TouchMaster 2.03 (OEM) on an Intel BL440ZX with its on-board ATI Rage Pro Turbo AGP.
rem Put the disk image next to 86box.cfg in TouchMaster-2.03-OEM first (see README).
start "" "%~dp0MasterPPBox.exe" -P "%~dp0TouchMaster-2.03-OEM" -R "%~dp0roms"
