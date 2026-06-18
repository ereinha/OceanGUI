
I want to make a GUI software to interface with an Ocean spectrometer using the seabreeze backend:
https://github.com/ap--/python-seabreeze/blob/main/docs/source/quickstart.rst
The details are below. Code up a solution.

Example minimal code:
from seabreeze.spectrometers import Spectrometer, list_devices
spec = Spectrometer.from_first_available()
spec.integration_time_micros(single_time)
wavelengths = spec.wavelengths()
intensities = spec.intensities()

Arguments/settings options:
Total integration time (can’t use both number and total time)
Number of integrations (can’t use both number and total time)
Single integration time
Down time between integrations

GUI
Side by side of current integration and average integration
Before the plots render it should show example dummy axes as a placeholder
Buttons to toggle uncertainty bars and bands (1sigma, 2 sigma)
Require filename before run starts
Store picture for total integration
Store csv file with integration time wavelengths and intensities
Button to save total integration figure with bars/bands added
Automatically save average integration with no bars/bands
Automatically save average integration in red with no bars/bands and each individual integration in grey behind the red total integration

Should have an automatic install bash script that creates an environment and a basic help menu in the GUI
Needs also a save file path as part of the repo folder
And the install should create a desktop shortcut (thumbnail picture can just be a cartoon plot of white background, black border, red spectrum line)
Needs to be able to build/install/setup and run on a windows machine and on linux both