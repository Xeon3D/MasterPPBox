@echo off
rem Midway TouchMaster 3.0x (ALPHA10) on an Intel BL440ZX with its on-board ATI Rage Pro Turbo AGP.
rem Put the disk image next to 86box.cfg in TouchMaster-3.0x-ALPHA10 first (see README).
start "" "%~dp0MasterPPBox.exe" -P "%~dp0TouchMaster-3.0x-ALPHA10" -R "%~dp0roms"
