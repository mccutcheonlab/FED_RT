
# Under construction👷‍♂️🚧⚠️


# RTFEDPi

![Banner Image](https://github.com/Htbibalan/FED_RT/blob/RTFEDPi/source/RTFED_Pi_Images/Cover.png)



* RTFEDPi is the Raspberry Pi variant of the classic ([RTFED](https://github.com/mccutcheonlab/FED_RT/tree/main)) and  is an open-source versatile tool for home-cage monitoring of behaviour and fiber photometry recording in mice. The RTFEDPi comes with 3 separate GUIs including RTFED(PiOS), RTFED(PiCAM) and RTFED(PiTTL). This system is developed as a home-cage setup to incorporate [FED3](https://github.com/KravitzLabDevices/FED3/wiki) units with TDT [RZ10](https://www.tdt.com/docs/hardware/rz10-lux-integrated-processor/) photometry processor for TTL-locked brain recording or to couple with USB cameras to capture event-triggered videos of behaviour.


# RTFED(PiOS)
RTFED(PiOS) can be used to remotely monitor feeding behaviour and other interactions made by mice on FED3, the data is automatically transferred to a Google spreadsheet where you can view it or define alarm notification using the Google Apps Scripts. Using the RTFEDPiOS you can also change the Mode of your FED3s without the hassle of poking one by one! However, if you are just aiming for monitoring feeding behaviour, we recommend using the basic([RTFED](https://github.com/mccutcheonlab/FED_RT/tree/main)) on Windows. 
![RTFED_PiOS](https://github.com/Htbibalan/FED_RT/blob/RTFEDPi/source/RTFED_Pi_Images/RTFED_Pi.png)


# RTFED(PiCAM)
RTFED(PiCAM) is an additional feature to the basic RTFED where you can enhance your behavioural studies by having event-triggered video recording. Primarily the RTFED(PiCAM) can record videos of mice using common USB cameras after taking Pellets, making Left or Right pokes or a combination of All of these events. Videos are limited to 30 sec length to capture only relevant behaviours while saving storage space, in this configuration, e.g. after taking a pellet, the GUI records the behaviour for 30 sec, if another pellet is taken within this 30 sec, it keeps recording for an extra 30 sec until no more pellet is taken.
![RTFED_PiCAM](https://github.com/Htbibalan/FED_RT/blob/RTFEDPi/source/RTFED_Pi_Images/RTFED(PiCAM).png)

# RTFED(PiTTL)
The TTL station of RTFED logs behavioural events made on FED3 devices and transmit them to the TDT RZ10 processors as TTL pulses. This feature enables you to study event-locked signals in your experiments. However the PiTTL version does not send data online to reduce any processing load that might delay the rapid TTL puls transmission.

![RTFED_PiTTL](https://github.com/Htbibalan/HOME_PHOTOMETRY/blob/main/source/RTFED(PiTTL).png)




# How to use RTFED on a Raspberry Pi?
##### To use RTFEDPi, first you need to follow most of the instructions explained on our main repository ([RTFED](https://github.com/mccutcheonlab/FED_RT/tree/main)), that includes updating your FED3 devices with RTFED library;  if you need to use the PiCAM system, you will need to also follow the instructions to make a Google project and the other setting on a Google spreadsheet, otherwise, to use the PiTTL system, you only need to update your FED3 firmware with RTFED library.



🚧🚧👷‍♂️🚧🚧🚧🚧👷‍♂️🚧🚧🚧🚧⚠️🚧⚠️🚧⚠️🚧⚠️🚧🚧🚧🚧👷‍♂️🚧








# Extra (For expert users who want to make changes in the codes)
You can use either the [.yml file](https://github.com/Htbibalan/FED_RT/tree/main/source/ENV_FILES) to create a separate environment for your RTFED python code, or use the requirement.txt file from the same folder to get the required  python packages. Follow the instructions on [ANACONDA_CHEAT_SHEET](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf), but basically download the above mentioned files and move them to your anaconda environments directory, open your anaconda terminal and navigate to to the directory where the RTFED.yml is located and run the command below:

                conda env create -f RTFED.yml

Alternatively you can use the requirement.txt file to either update packages in your base/current environment or making an env from the scratch,simply navigate to the directory where you have the requirements.txt located, and run the following command:

                pip install -r requirements.txt


# License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

# Author of this repository
Hamid Taghipourbibalan, Ph.D. student at [McCutcheon_lab](https://www.mccutcheonlab.com/) at UiT The Arctic University of Norway.




















