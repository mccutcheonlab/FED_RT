
/*
  Feeding experimentation device 3 (FED3) library
  Code by Lex Kravitz, adapted to Arduino library format by Eric Lin
  alexxai@wustl.edu
  erclin@ucdavis.edu
  December 2020 

  The first FED device was developed by Nguyen at al and published in 2016:
  https://www.ncbi.nlm.nih.gov/pubmed/27060385

  FED3 includes hardware and code from:
  *** Adafruit, who made the hardware breakout boards and associated code we used in FED ***

  Cavemoa's excellent examples of datalogging with the Adalogger:
  https://github.com/cavemoa/Feather-M0-Adalogger

  Arduino Time library http://playground.arduino.cc/code/time
  Maintained by Paul Stoffregen https://github.com/PaulStoffregen/Time

  This project is released under the terms of the Creative Commons - Attribution - ShareAlike 3.0 license:
  human readable: https://creativecommons.org/licenses/by-sa/3.0/
  legal wording: https://creativecommons.org/licenses/by-sa/3.0/legalcode
  Copyright (c) 2019, 2020 Lex Kravitz



This script was edited by Francois Ducroux (Paris-Saclay university) who was a guest student - Spring 2023 at McCutcheon lab at UiT The Arctic University of Norway in Tromsø.
Francois Ducroux added the snippet of the code which allows the user to define the type of pellets used in the experiment.
The user can define the type of pellets used in the experiment ( When setting Device number by poking left and right while FED3 boots up) by setting the variable "pelletType" to the desired value.
The pellet type will be added to the filename of data stored on the SD card. If you are not interested in this feature, just ignore the pellettype settings during bootup.
Moreover, Francois added the ClosedEconomy mode to the set of modes available to choose from during bootup.

The script was further adjusted by Hamid Taghipourbibalan (Ph.D. Student at McCutcheon Lab | UiT The Arctic University of Norway) in 2024.
The changes are explained in the RTFED project https://github.com/mccutcheonlab/FED_RT/tree/main 
Briefly, the code enables the FED3 to send data directly via serial communication(USB ports) to a computer or a Raspberry Pi or Arduino board.
It also logs PelletInWell (when the pellet is detected in the well but not taken by the animal),
also logs an event called JAM which is used to send a notification to the user via Google Spreadsheet.The device stops after 5 attempts to clear jam. 
Moreover Baudrate was set to 115200 to increase the speed of data transfer via serial communication for synchronization with TDT photometry system.

Latest feature added Dec 2024: FED3 listens to serial commands from the host computer to set the time. The command should be in the format "SET_TIME:YYYY,MM,DD,HH,MM,SS" where YYYY is the year, MM is the month, DD is the day, HH is the hour, MM is the minute, and SS is the second. The time is set to the time specified in the command. The FED3 will respond with "TIME_SET_OK" if the time was set successfully, or "TIME_SET_FAIL" if the time was not set successfully.

Latest feature added March 2025: FED3 listents to POKE command from RTFED GUI which helps to identify the devices without hassle 

Latest feature May 2025: FED3 listens to serial commands from the host computer to set the mode. The command should be in the format "SET_MODE:<0-15>" where <0-15> is the mode number. The FED3 will respond with "MODE_SET_OK" if the mode was set successfully, or "MODE_SET_FAIL" if the mode was not set successfully.
@htbibalan@uit.no
@james.e.mccutcheon@uit.no


*/
/**************************************************************************************************************************************************
                                                                                                        Startup stuff
**************************************************************************************************************************************************/
#include "Arduino.h"
#include "FED3.h"

//  Start FED3 and RTC objects
FED3 *pointerToFED3;
RTC_PCF8523 rtc; 

//  Interrupt handlers
static void outsidePelletTriggerHandler(void) {
  pointerToFED3->pelletTrigger();
}

static void outsideLeftTriggerHandler(void) {
  pointerToFED3->leftTrigger();
}

static void outsideRightTriggerHandler(void) {
  pointerToFED3->rightTrigger();
}



/**************************************************************************************************************************************************
                                                                                                            Main loop
**************************************************************************************************************************************************/
// Adding a new function to handle commands from Windows PC
void FED3::checkSerialCommands() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    // SET_TIME:YYYY,MM,DD,HH,MM,SS
    if (line.startsWith("SET_TIME:")) {
      line.remove(0, 9); // remove "SET_TIME:"
      int year, month, day, hour, minute, second;
      char cstr[50];
      line.toCharArray(cstr, sizeof(cstr));
      int parsed = sscanf(cstr, "%d,%d,%d,%d,%d,%d",
                          &year, &month, &day,
                          &hour, &minute, &second);
      if (parsed == 6) {
        rtc.adjust(DateTime(year, month, day, hour, minute, second));
        Serial.println("TIME_SET_OK");
      } else {
        Serial.println("TIME_SET_FAIL");
      }

    // SET_MODE:<0–15>
    } else if (line.startsWith("SET_MODE:")) {
      line.remove(0, 9); // remove "SET_MODE:"
      int mode = line.toInt();
      if (mode >= 0 && mode <= 15) {
        FEDmode = mode;
        writeFEDmode();            // Save new mode to SD
        Serial.println("MODE_SET_OK");
        delay(200);
        NVIC_SystemReset();        // Reboot into new mode
      } else {
        Serial.println("MODE_SET_FAIL");
      }

    // TRIGGER_POKE
    } else if (line == "TRIGGER_POKE") {
      simulatePoke();              // Call the function to simulate a poke event
    }
  }
}


void FED3::run() {
  if (stopLogging){
    return;
  }
  // Check if there's a command from the host computer to set time
  checkSerialCommands();



  //This should be called at least once per loop.  It updates the time, updates display, and controls sleep 
  if (digitalRead(PELLET_WELL) == HIGH) {  //check for pellet
    PelletAvailable = false;
  }
  DateTime now = rtc.now();
  currentHour = now.hour(); //useful for timed feeding sessions
  currentMinute = now.minute(); //useful for timed feeding sessions
  currentSecond = now.second(); //useful for timed feeding sessions
  unixtime = now.unixtime();
  ReadBatteryLevel();
  UpdateDisplay();
  goToSleep();
}

/**************************************************************************************************************************************************
                                                                                                    Poke functions
**************************************************************************************************************************************************/
//log left poke
void FED3::logLeftPoke(bool simulated) {
  if (stopLogging){
    return;
  }
  leftPokeTime = millis();
  LeftCount++;
  leftInterval = 0.0;
  if (!simulated) {  // Only wait if this is a real poke
    while (digitalRead(LEFT_POKE) == LOW) {}  
  }
  leftInterval = millis() - leftPokeTime;
  UpdateDisplay();
  DisplayLeftInt();
  if (leftInterval < minPokeTime) {
    Event = "LeftShort";
  } else {
    Event = "Left";
  }
  logdata();
  Left = false;
}


//log right poke
void FED3::logRightPoke(bool simulated) {
  if (stopLogging){
    return;
  }
  rightPokeTime = millis();
  RightCount++;
  rightInterval = 0.0;
  if (!simulated) {  // Only wait if this is a real poke
    while (digitalRead(RIGHT_POKE) == LOW) {}
  }
  rightInterval = millis() - rightPokeTime;
  UpdateDisplay();
  DisplayRightInt();
  if (rightInterval < minPokeTime) {
    Event = "RightShort";
  } else {
    Event = "Right";
  }
  logdata();
  Right = false; 
}



void FED3::randomizeActivePoke(int max){
  //Store last active side and randomize
  byte lastActive = activePoke;
  activePoke = random (0, 2);

  //Increment consecutive active pokes, or reset consecutive to zero
  if (activePoke == lastActive) {
    consecutive ++;
  }
  else {
    consecutive = 0;
  }
  
  //if consecutive pokes are too many, swap pokes
  if (consecutive >= max){
    if (activePoke == 0) {
      activePoke = 1;
    }
    else if (activePoke == 1) {
      activePoke = 0;
    }
    consecutive = 0;
    }
}

/**************************************************************************************************************************************************
                                                                                                    POKE TRIGGER function for RTFED
**************************************************************************************************************************************************/

void FED3::simulatePoke() {
  Serial.println("SIMULATED_POKE");  // Confirm command received
  // Simulate a poke event (randomly choosing left or right poke)
  if (random(0, 2) == 0) {
      logLeftPoke(true);  // Simulated poke: bypass waiting
  } else {
      logRightPoke(true);
  }
}








/**************************************************************************************************************************************************
                                                                                                    Feeding functions
**************************************************************************************************************************************************/
void FED3::Feed(int pulse, bool pixelsoff) {
  if (stopLogging){
    return;
  }
  // Exit immediately if a jam has occurred
  if (jamOccurred == true) {
    return; // Exit the function immediately
  }

  //Run this loop repeatedly until statement below is false
  bool pelletDispensed = false;
  
  do {	
  
    if (pelletDispensed == false) {
      pelletDispensed = RotateDisk(-300);
    }

    if (pixelsoff==true){
      pixelsOff();
    }
    
    //If pellet is detected during or after this motion
    if (pelletDispensed == true) {
    ReleaseMotor();
    pelletTime = millis();

    // Log PelletInWell event when the pellet is detected in the well
    Event = "PelletInWell";
    logdata();

    display.fillCircle(25, 99, 5, BLACK);
    display.refresh();
    retInterval = (millis() - pelletTime);

    //while pellet is present and under 60s has elapsed
    while (digitalRead(PELLET_WELL) == LOW && retInterval < 60000) {
        retInterval = (millis() - pelletTime);
        DisplayRetrievalInt();

        // Log pokes while pellet is present 
        if (digitalRead(LEFT_POKE) == LOW) {
            leftPokeTime = millis();
            LeftCount++;
            leftInterval = 0.0;
            while (digitalRead(LEFT_POKE) == LOW) {}  //Hang here until poke is clear
            leftInterval = (millis() - leftPokeTime);
            UpdateDisplay();
            Event = "LeftWithPellet";
            logdata();
        }

        if (digitalRead(RIGHT_POKE) == LOW) {
            rightPokeTime = millis();
            RightCount++;
            rightInterval = 0.0;
            while (digitalRead(RIGHT_POKE) == LOW) {}  //Hang here until poke is clear
            rightInterval = (millis() - rightPokeTime);
            UpdateDisplay();
            Event = "RightWithPellet";
            logdata();
        }
    }
    
    // After 60s has elapsed
    while (digitalRead(PELLET_WELL) == LOW) { //if pellet is not taken after 60 seconds, wait here and go to sleep
        run();
        //Log pokes while pellet is present 
        if (digitalRead(LEFT_POKE) == LOW) {             //If left poke is triggered
          leftPokeTime = millis();
          LeftCount ++;
          leftInterval = 0.0;
          while (digitalRead (LEFT_POKE) == LOW) {}  //Hang here until poke is clear
          leftInterval = (millis()-leftPokeTime);
          UpdateDisplay();
          Event = "LeftWithPellet";
          logdata();
          }

        if (digitalRead(RIGHT_POKE) == LOW) {            //If right poke is triggered
          rightPokeTime = millis();
          RightCount ++;
           rightInterval = 0.0;
          while (digitalRead (RIGHT_POKE) == LOW) {}  //Hang here until poke is clear
          rightInterval = (millis()-rightPokeTime);
          UpdateDisplay();
          Event = "RightWithPellet";
          logdata();       
          }
      }

      ReleaseMotor ();
      PelletCount++;
      
      // If pulse duration is specified, send pulse from BNC port      
      if (pulse > 0){
        BNC (pulse, 1);  
      }
      
      Left = false;
      Right = false;
      Event = "Pellet";
      
      //calculate InterPelletInterval
      DateTime now = rtc.now();
      interPelletInterval = now.unixtime() - lastPellet;  //calculate time in seconds since last pellet logged
      lastPellet  = now.unixtime();
     
      logdata();
      numMotorTurns = 0; //reset numMotorTurns
      PelletAvailable = true;
      UpdateDisplay();
      
      break;
    }

    if (PelletAvailable == false){
        pelletDispensed = dispenseTimer_ms(1500);  //delay between pellets that also checks pellet well
        numMotorTurns++;

        //Jam clearing movements
        if (pelletDispensed == false) {
          if (numMotorTurns % 5 == 0) {
            pelletDispensed = MinorJam();
          }
        }
        if (pelletDispensed == false) {
          if (numMotorTurns % 10 == 0 and numMotorTurns % 20 != 0) {
            pelletDispensed = VibrateJam();
          }
        }
        if (pelletDispensed == false) {
          if (numMotorTurns % 20 == 0) {
            pelletDispensed = ClearJam();
          }
        }
        if (pelletDispensed == false) {
          if (numMotorTurns % 50 == 0) { // Increased from 30 to 50 for more attempts
            Alarm();
          }
        }
    }
  } while (PelletAvailable == false && jamOccurred == false); // Added jamOccurred condition
}

//minor movement to clear jam
bool FED3::MinorJam(){
  return RotateDisk(100);
}
  
//vibration movement to clear jam
bool FED3::VibrateJam() {
    DisplayJamClear();
  
  //simple debounce to ensure pellet is out for at least 250ms
  if (dispenseTimer_ms(250)) {
    display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
    return true;
  } 
  for (int i = 0; i < 30; i++) {
    if (RotateDisk(120)) {
      display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
      return true;
    }
    if (RotateDisk(-60)) {
      display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
      return true;
    }
  }
  return false;
}

//full rotation to clear jam
bool FED3::ClearJam() {
    DisplayJamClear();
  
  if (dispenseTimer_ms(250)) {
    display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
    return true;
  }
  
  for (int i = 0; i < 21 + random(0, 20); i++) {
    if (RotateDisk(-i * 4)) {
      display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
      return true;
    }
  }
  
  if (dispenseTimer_ms(250)) {
    display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
    return true;
  }
  
  for (int i = 0; i < 21 + random(0, 20); i++) {
    if (RotateDisk(i * 4)) {
      display.fillRect (5, 15, 120, 15, WHITE);  //erase the "Jam clear" text without clearing the entire screen by pasting a white box over it
      return true;
    }
  }
  
  return false;
}

bool FED3::RotateDisk(int steps) {
  if (jamOccurred == true) {
    return false; // Do not attempt to move the motor
  }
  digitalWrite (MOTOR_ENABLE, HIGH);  //Enable motor driver
  for (int i = 0; i < (steps>0?steps:-steps); i++) {	
  
    if (digitalRead(LEFT_POKE) == LOW) {             //If left poke is triggered
       leftPokeTime = millis();
       LeftCount ++;
       leftInterval = 0.0;
       while (digitalRead (LEFT_POKE) == LOW) {}  //Hang here until poke is clear
       leftInterval = (millis() - leftPokeTime);
       UpdateDisplay();
       Event = "LeftDuringDispense";
       logdata();
     }

     if (digitalRead(RIGHT_POKE) == LOW) {            //If right poke is triggered
       rightPokeTime = millis();
       RightCount ++;
       rightInterval = 0.0;
       while (digitalRead (RIGHT_POKE) == LOW) {}  //Hang here until poke is clear
       rightInterval = (millis() - rightPokeTime);
       UpdateDisplay();
       Event = "RightDuringDispense";
       logdata();
     }
    
    if (steps > 0)
      stepper.step(1);
    else
      stepper.step(-1);	  
    for (int j = 0; j < 20; j++){
      delayMicroseconds(100);		
      if (digitalRead (PELLET_WELL) == LOW) {
        delayMicroseconds(100);
        // Debounce
        if (digitalRead (PELLET_WELL) == LOW) {
          ReleaseMotor ();
          return true;
        }
      }
    }
    }
  ReleaseMotor ();
  return false;
}

//Function for delaying between motor movements, but also ending this delay if a pellet is detected
bool FED3::dispenseTimer_ms(int ms) {
  for (int i = 1; i < ms; i++) {
    for (int j = 0; j < 10; j++) {
        delayMicroseconds(100);		
    if (digitalRead (PELLET_WELL) == LOW) {
      delayMicroseconds(100);
      // Debounce
      if (digitalRead (PELLET_WELL) == LOW) {
        return true;
      }
    }
  }
  }
  return false;
}

//Timeout function
void FED3::Timeout(int seconds) {
  int timeoutStart = millis();
  while ((millis() - timeoutStart) < (seconds*1000)) {
    delay (1);
    int displayUpdated = millis();
    if (millis() - displayUpdated < 1000) {
      display.fillRect (5, 20, 200, 25, WHITE); //erase the data on screen without clearing the entire screen by pasting a white box over it
      display.setCursor(6, 36);
      display.print("Timeout: ");
      display.print(round(seconds - ((millis() - timeoutStart)) / 1000));
      display.refresh();
    }

    if (digitalRead(LEFT_POKE) == LOW) {             //If left poke is triggered
      leftPokeTime = millis();
      LeftCount ++;
      leftInterval = 0.0;
      while (digitalRead (LEFT_POKE) == LOW) {}  //Hang here until poke is clear
      leftInterval = (millis() - leftPokeTime);
      UpdateDisplay();
      Event = "LeftinTimeOut";
      logdata();
    }

    if (digitalRead(RIGHT_POKE) == LOW) {            //If right poke is triggered
      rightPokeTime = millis();
      RightCount ++;
      rightInterval = 0.0;
      while (digitalRead (RIGHT_POKE) == LOW) {}  //Hang here until poke is clear
      rightInterval = (millis() - rightPokeTime);
      UpdateDisplay();
      Event = "RightinTimeout";
      logdata();
    }
  }

  display.fillRect (5, 20, 100, 25, WHITE);  //erase the data on screen without clearing the entire screen by pasting a white box over it
  UpdateDisplay();
  Left = false;
  Right = false;
} 

/**************************************************************************************************************************************************
                                                                                           Audio and neopixel stimuli
**************************************************************************************************************************************************/
void FED3::ConditionedStimulus(int duration) {
  tone (BUZZER, 4000, duration);
  pixelsOn(0,0,10,0);  //blue light for all
}

void FED3::Click() {
  tone (BUZZER, 800, 8);
}

void FED3::Tone(int freq, int duration){
  tone (BUZZER, freq, duration);
}

void FED3::stopTone(){
  noTone (BUZZER);
}


void FED3::Noise(int duration) {
  // White noise to signal errors
  for (int i = 0; i < duration/50; i++) {
    tone (BUZZER, random(50, 250), 50);
    delay(duration/50);
  }
}

//Turn all pixels on to a specific color
void FED3::pixelsOn(int R, int G, int B, int W) {
  digitalWrite (MOTOR_ENABLE, HIGH);  //ENABLE motor driver
  delay(2); //let things settle
  for (uint16_t i = 0; i < 8; i++) {
    strip.setPixelColor(i, R, G, B, W);
    strip.show();
  }
}

//Turn all pixels off
void FED3::pixelsOff() {
  digitalWrite (MOTOR_ENABLE, HIGH);  //ENABLE motor driver
  delay (2); //let things settle
    for (uint16_t i = 0; i < strip.numPixels(); i++) {
    strip.setPixelColor(i, 0,0,0,0);
    strip.show();   
  }
  digitalWrite (MOTOR_ENABLE, LOW);  //disable motor driver and neopixels
}

//colorWipe does a color wipe from left to right
void FED3::colorWipe(uint32_t c, uint8_t wait) {
  digitalWrite (MOTOR_ENABLE, HIGH);  //ENABLE motor driver
  delay(2); //let things settle
  for (uint16_t i = 0; i < 8; i++) {
    strip.setPixelColor(i, c);
    strip.show();
    delay(wait);
  }
  digitalWrite (MOTOR_ENABLE, LOW);  ////disable motor driver and neopixels
  delay(2); //let things settle
}

// Visual tracking stimulus - left-most pixel on strip
void FED3::leftPixel(int R, int G, int B, int W) {
  digitalWrite (MOTOR_ENABLE, HIGH);
  delay(2); //let things settle
  strip.setPixelColor(0, R, G, B, W);
  strip.show();
}

// Visual tracking stimulus - right-most pixel on strip
void FED3::rightPixel(int R, int G, int B, int W) {
  digitalWrite (MOTOR_ENABLE, HIGH);
  delay(2); //let things settle
  strip.setPixelColor(7, R, G, B, W);
  strip.show();
}

// Visual tracking stimulus - left poke pixel
void FED3::leftPokePixel(int R, int G, int B, int W) {
  digitalWrite (MOTOR_ENABLE, HIGH);
  delay(2); //let things settle
  strip.setPixelColor(9, R, G, B, W);
  strip.show();
}

// Visual tracking stimulus - right poke pixel
void FED3::rightPokePixel(int R, int G, int B, int W) {
  digitalWrite (MOTOR_ENABLE, HIGH);
  delay(2); //let things settle
  strip.setPixelColor(8, R, G, B, W);
  strip.show();
}

//Short helper function for blinking LEDs and BNC out port
void FED3::Blink(byte PIN, byte DELAY_MS, byte loops) {
  for (byte i = 0; i < loops; i++)  {
    digitalWrite(PIN, HIGH);
    delay(DELAY_MS);
    digitalWrite(PIN, LOW);
    delay(DELAY_MS);
  }
}

//Simple function for sending square wave pulses to the BNC port
void FED3::BNC(int DELAY_MS, int loops) {
  for (int i = 0; i < loops; i++)  {
    digitalWrite(BNC_OUT, HIGH);
    digitalWrite(GREEN_LED, HIGH);
    delay(DELAY_MS);
    digitalWrite(BNC_OUT, LOW);
    digitalWrite(GREEN_LED, LOW);
    delay(DELAY_MS);
  }
}


void FED3::disableInputs() {
    // Disable motor driver
    digitalWrite(MOTOR_ENABLE, LOW);
    // Detach interrupts
    detachInterrupt(digitalPinToInterrupt(PELLET_WELL));
    detachInterrupt(digitalPinToInterrupt(LEFT_POKE));
    detachInterrupt(digitalPinToInterrupt(RIGHT_POKE));
    // Set all other control pins to LOW
    // digitalWrite(A2, LOW);
    // digitalWrite(A3, LOW);
    // digitalWrite(A4, LOW);
    // digitalWrite(A5, LOW);
    // digitalWrite(BNC_OUT, LOW);
    Serial.println("Inputs Disabled and Logging Stopped"); // Added for debugging
}


//Simple function for generating a beeping pattern when alarm needed
void FED3::Alarm() {
  Event="JAM";
  logdata();
  stopLogging = true;
  disableInputs();
  jamOccurred = true;  // Set flag to indicate jam has occurred
  // Removed the beeping code and infinite loop
}

//More advanced function for controlling pulse width and frequency for the BNC port
void FED3::pulseGenerator(int pulse_width, int frequency, int repetitions){  // freq in Hz, width in ms, loops in number of times
  for (byte j = 0; j < repetitions; j++) {
    digitalWrite(BNC_OUT, HIGH);
    digitalWrite(GREEN_LED, HIGH);
    delay(pulse_width);  //pulse high for width
    digitalWrite(BNC_OUT, LOW);
    digitalWrite(GREEN_LED, LOW);
    long temp_delay = (1000 / frequency) - pulse_width;
    if (temp_delay < 0) temp_delay = 0;  //if temp delay <0 because parameters are set wrong, set it to 0 so FED3 doesn't crash O_o
    delay(temp_delay); //pin low 
  }
}

void FED3::ReadBNC(bool blinkGreen){
    pinMode(BNC_OUT, INPUT_PULLDOWN);
    BNCinput=false;
    if (digitalRead(BNC_OUT) == HIGH)
  {
    delay (1);
    if (digitalRead(BNC_OUT) == HIGH)
    {
      if (blinkGreen == true)
      {
        digitalWrite(GREEN_LED, HIGH);
        delay (25);
        digitalWrite(GREEN_LED, LOW);
      }     
         BNCinput=true;
    }
    }
}
    

/**************************************************************************************************************************************************
                                                                                                     Display functions
**************************************************************************************************************************************************/
void FED3::UpdateDisplay() {
  //Box around data area of screen
  display.drawRect (5, 45, 158, 70, BLACK);
  
  display.setCursor(5, 15);
  display.print("RTT:");
  display.println(FED);
  display.setCursor(6, 15);  // this doubling is a way to do bold type
  display.print("RTT:");
  display.fillRect (6, 20, 200, 22, WHITE);  //erase text under battery row without clearing the entire screen
  display.fillRect (35, 46, 120, 68, WHITE);  //erase the pellet data on screen without clearing the entire screen 
  display.setCursor(5, 36); //display which sketch is running
  
  //write the first 8 characters of sessiontype:
  display.print(sessiontype.charAt(0));
  display.print(sessiontype.charAt(1));
  display.print(sessiontype.charAt(2));
  display.print(sessiontype.charAt(3));
  display.print(sessiontype.charAt(4));
  display.print(sessiontype.charAt(5));
  display.print(sessiontype.charAt(6));
  display.print(sessiontype.charAt(7));

  if (DisplayPokes == 1) {
    display.setCursor(35, 65);
    display.print("Left: ");
    display.setCursor(95, 65);
    display.print(LeftCount);
    display.setCursor(35, 85);
    display.print("Right:  ");
    display.setCursor(95, 85);
    display.print(RightCount);
  }
  
  display.setCursor(35, 105);
  display.print("Pellets:");
  display.setCursor(95, 105);
  display.print(PelletCount);
  
  if (DisplayTimed==true) {  //If it's a timed Feeding Session
    DisplayTimedFeeding();
  }
  
  DisplayBattery();
  DisplayDateTime();
  DisplayIndicators();
  display.refresh();
}

void FED3::DisplayDateTime(){
  // Print date and time at bottom of the screen
  DateTime now = rtc.now();
  display.setCursor(0, 135);
  display.fillRect (0, 123, 200, 60, WHITE);
  display.print(now.month());
  display.print("/");
  display.print(now.day());
  display.print("/");
  display.print(now.year());
  display.print("      ");
  if (now.hour() < 10)
    display.print('0');      // Trick to add leading zero for formatting
  display.print(now.hour());
  display.print(":");
  if (now.minute() < 10)
    display.print('0');      // Trick to add leading zero for formatting
  display.print(now.minute());
}

void FED3::DisplayIndicators(){
  // Pellet circle
  display.fillCircle(25, 99, 5, WHITE); //pellet
  display.drawCircle(25, 99, 5, BLACK);

  //Poke indicators
  if (DisplayPokes == 1) { //only make active poke indicators if DisplayPokes==1
    //Active poke indicator triangles
    if (activePoke == 0) {
      display.fillTriangle (20, 55, 26, 59, 20, 63, WHITE);
      display.fillTriangle (20, 75, 26, 79, 20, 83, BLACK);
    }
    if (activePoke == 1) {
      display.fillTriangle (20, 75, 26, 79, 20, 83, WHITE);
      display.fillTriangle (20, 55, 26, 59, 20, 63, BLACK);
    }
  }
}

void FED3::DisplayBattery(){
  //  Battery graphic showing bars indicating voltage levels
  if (numMotorTurns == 0) {
    display.fillRect (117, 2, 40, 16, WHITE);
    display.drawRect (116, 1, 42, 18, BLACK);
    display.drawRect (157, 6, 6, 8, BLACK);
  }
  //4 bars
  if (measuredvbat > 3.85 & numMotorTurns == 0) {
    display.fillRect (120, 4, 7, 12, BLACK);
    display.fillRect (129, 4, 7, 12, BLACK);
    display.fillRect (138, 4, 7, 12, BLACK);
    display.fillRect (147, 4, 7, 12, BLACK);
  }

  //3 bars
  else if (measuredvbat > 3.7 & numMotorTurns == 0) {
    display.fillRect (119, 3, 26, 13, WHITE);
    display.fillRect (120, 4, 7, 12, BLACK);
    display.fillRect (129, 4, 7, 12, BLACK);
    display.fillRect (138, 4, 7, 12, BLACK);
  }

  //2 bars
  else if (measuredvbat > 3.55 & numMotorTurns == 0) {
    display.fillRect (119, 3, 26, 13, WHITE);
    display.fillRect (120, 4, 7, 12, BLACK);
    display.fillRect (129, 4, 7, 12, BLACK);
  }

  //1 bar
  else if (numMotorTurns == 0) {
    display.fillRect (119, 3, 26, 13, WHITE);
    display.fillRect (120, 4, 7, 12, BLACK);
  }
  
  //display voltage
  display.setTextSize(2);
  display.setFont(&Org_01);

  display.fillRect (86, 0, 28, 12, WHITE);
  display.setCursor(87, 10);
  display.print(measuredvbat, 1);
  display.setFont(&FreeSans9pt7b);
  display.setTextSize(1);
  
  //display temp/humidity sensor indicator if present
  if (tempSensor == true){
    display.setTextSize(1);
    display.setFont(&Org_01);
    display.setCursor(89, 18);
    display.print("TH");
    display.setFont(&FreeSans9pt7b);
    display.setTextSize(1);
  }
}

//Display "Check SD Card!" if there is a card error
void FED3::DisplaySDError() {
  display.clearDisplay();
  display.setCursor(20, 40);
  display.println("   Check");
  display.setCursor(10, 60);
  display.println("  SD Card!");
  display.refresh();
}

//Display text when FED is clearing a jam
void FED3::DisplayJamClear() {
  display.fillRect (6, 20, 200, 22, WHITE);  //erase the data on screen without clearing the entire screen by pasting a white box over it
  display.setCursor(6, 36);
  display.print("Clearing jam");
  display.refresh();
}

//Display pellet retrieval interval
void FED3::DisplayRetrievalInt() {
  display.fillRect (85, 22, 70, 15, WHITE); 
  display.setCursor(90, 36);
  if (retInterval<59000){
    display.print (retInterval);
    display.print ("ms");
  }
  display.refresh();
}

//Display left poke duration
void FED3::DisplayLeftInt() {
  display.fillRect (85, 22, 70, 15, WHITE);  
  display.setCursor(90, 36);
  if (leftInterval<10000){
    display.print (leftInterval);
    display.print ("ms");
  }
  display.refresh();
}

//Display right poke duration
void FED3::DisplayRightInt() {
  display.fillRect (85, 22, 70, 15, WHITE);  
  display.setCursor(90, 36);
  if (rightInterval<10000){
    display.print (rightInterval);
    display.print ("ms");
  }
  display.refresh();
}

void FED3::StartScreen(){
  if (ClassicFED3==false){
    display.setTextSize(3);
    display.setTextColor(BLACK);
    display.clearDisplay();
    display.setCursor(15, 55);
    display.print("FED3");
      
    //print filename on screen
    display.setTextSize(1);
    display.setCursor(2, 138);
    display.print(filename);

    //Display FED verison number at startup
    display.setCursor(2, 120);
    display.print("v: ");
    display.print(VER);
    display.print("_");
    display.print(sessiontype.charAt(0));
    display.print(sessiontype.charAt(1));
    display.print(sessiontype.charAt(2));
    display.print(sessiontype.charAt(3));
    display.print(sessiontype.charAt(4));
    display.print(sessiontype.charAt(5));
    display.print(sessiontype.charAt(6));
    display.print(sessiontype.charAt(7));
    display.refresh();
    DisplayMouse();
  }
}

void FED3::DisplayTimedFeeding(){
  display.setCursor(35, 65);
  display.print (timedStart);
  display.print (":00 to ");
  display.print (timedEnd);
  display.print (":00");
}

void FED3::DisplayMinPoke(){
  display.setCursor(115, 65);
  display.print ((minPokeTime/1000.0),1);
  display.print ("s");
  display.refresh();
}

void FED3::DisplayNoProgram(){
  display.clearDisplay();
  display.setCursor(15, 45);
  display.print ("No program");
  display.setCursor(16, 45);
  display.print ("No program");
  display.setCursor(15, 65);
  display.print ("resetting FED3...");
  display.refresh();
  for (int i = 0; i < 5; i++) {
    colorWipe(strip.Color(5, 0, 0), 25); // RED
    delay (20);
    colorWipe(strip.Color(0, 0, 0), 25); // clear
    delay (40);
  }
  NVIC_SystemReset();
}

void FED3::DisplayMouse() {
  //Draw animated mouse...
  for (int i = -50; i < 200; i += 15) {
    display.fillRoundRect (i + 25, 82, 15, 10, 6, BLACK);    //head
    display.fillRoundRect (i + 22, 80, 8, 5, 3, BLACK);      //ear
    display.fillRoundRect (i + 30, 84, 1, 1, 1, WHITE);      //eye
    //movement of the mouse
    if ((i / 10) % 2 == 0) {
      display.fillRoundRect (i, 84, 32, 17, 10, BLACK);      //body
      display.drawFastHLine(i - 8, 85, 18, BLACK);           //tail
      display.drawFastHLine(i - 8, 86, 18, BLACK);
      display.drawFastHLine(i - 14, 84, 8, BLACK);
      display.drawFastHLine(i - 14, 85, 8, BLACK);
      display.fillRoundRect (i + 22, 99, 8, 4, 3, BLACK);    //front foot
      display.fillRoundRect (i , 97, 8, 6, 3, BLACK);        //back foot
    }
    else {
      display.fillRoundRect (i + 2, 82, 30, 17, 10, BLACK);  //body
      display.drawFastHLine(i - 6, 91, 18, BLACK);           //tail
      display.drawFastHLine(i - 6, 90, 18, BLACK);
      display.drawFastHLine(i - 12, 92, 8, BLACK);
      display.drawFastHLine(i - 12, 91, 8, BLACK);
      display.fillRoundRect (i + 15, 99, 8, 4, 3, BLACK);    //foot
      display.fillRoundRect (i + 8, 97, 8, 6, 3, BLACK);     //back foot
    }
    display.refresh();
    delay (80);
    display.fillRect (i-25, 73, 95, 33, WHITE);
    previousFEDmode = FEDmode;
    previousFED = FED;
    
    // If one poke is pushed change mode
    if (FED3Menu == true or ClassicFED3 == true){
      if (digitalRead (LEFT_POKE) == LOW | digitalRead (RIGHT_POKE) == LOW) SelectMode();
    }
    
    // If both pokes are pushed edit device number
    if ((digitalRead(LEFT_POKE) == LOW) && (digitalRead(RIGHT_POKE) == LOW)) {
      tone (BUZZER, 1000, 200);
      delay(400);
      tone (BUZZER, 1000, 500);
      delay(200);
      tone (BUZZER, 3000, 600);
      colorWipe(strip.Color(2, 2, 2), 40); // Color wipe
      colorWipe(strip.Color(0, 0, 0), 20); // OFF
      EndTime = millis();
      SetFED = true;
      SetDeviceNumber();
    }
  }
}

/**************************************************************************************************************************************************
                                                                                                 SD Logging functions
**************************************************************************************************************************************************/
// Create new files on uSD for FED3 settings
void FED3::CreateFile() {
  digitalWrite (MOTOR_ENABLE, LOW);  //Disable motor driver and neopixel
  // see if the card is present and can be initialized:
  if (!SD.begin(cardSelect, SD_SCK_MHZ(4))) {
    error(2);
  }

  // create files if they dont exist and grab device name and ratio
  configfile = SD.open("DeviceNumber.csv", FILE_WRITE);
  configfile = SD.open("DeviceNumber.csv", FILE_READ);
  FED = configfile.parseInt();
  configfile.close();

  ratiofile = SD.open("FEDmode.csv", FILE_WRITE);
  ratiofile = SD.open("FEDmode.csv", FILE_READ);
  FEDmode = ratiofile.parseInt();
  ratiofile.close();

  startfile = SD.open("start.csv", FILE_WRITE);
  startfile = SD.open("start.csv", FILE_READ);
  timedStart = startfile.parseInt();
  startfile.close();

  stopfile = SD.open("stop.csv", FILE_WRITE);
  stopfile = SD.open("stop.csv", FILE_READ);
  timedEnd = stopfile.parseInt();
  stopfile.close();

  Pelletfile = SD.open("Pelletfile.csv", FILE_WRITE); 
  Pelletfile = SD.open("Pelletfile.csv", FILE_READ);
  PelletType = Pelletfile.parseInt();
  Pelletfile.close();

  // Name filename in format F###_MMDDYYNN, where MM is month, DD is day, YY is year, and NN is an incrementing number for the number of files initialized each day
  strcpy(filename, "FED_______________.CSV");  // placeholder filename
  getFilename(filename);
}

//Create a new datafile
void FED3::CreateDataFile () {
  digitalWrite (MOTOR_ENABLE, LOW);  //Disable motor driver and neopixel
  getFilename(filename);
  logfile = SD.open(filename, FILE_WRITE);
  if ( ! logfile ) {
    error(3);
  }
}

void FED3::writeHeader() {
  digitalWrite(MOTOR_ENABLE, LOW);  // Disable motor driver and neopixel

  // 1) Build the “base” header
  String header;
  if (! tempSensor) {
    header = "MM:DD:YYYY hh:mm:ss,"
             "Library_Version,Session_type,Device_Number,"
             "Battery_Voltage,Motor_Turns,FR,Event,Active_Poke,"
             "Left_Poke_Count,Right_Poke_Count,Pellet_Count,"
             "Block_Pellet_Count,Retrieval_Time,"
             "InterPelletInterval,Poke_Time";
  } else {
    header = "MM:DD:YYYY hh:mm:ss,Temp,Humidity,"
             "Library_Version,Session_type,Device_Number,"
             "Battery_Voltage,Motor_Turns,FR,Event,Active_Poke,"
             "Left_Poke_Count,Right_Poke_Count,Pellet_Count,"
             "Block_Pellet_Count,Retrieval_Time,"
             "InterPelletInterval,Poke_Time";
  }

  // 2) Append either the 4 bandit columns, or 4 blanks
  if (sessiontype == "Bandit8020"
   || sessiontype == "DetBandit"
   || sessiontype == "ProbRev")
  {
    header += ",PelletsOrTrialToSwitch,Prob_left,Prob_right,High_prob_poke";
  } else {
    header += ",,,,";   // four empty placeholders
  }

  // 3) Write it all out in one go
  logfile.println(header);
  logfile.close();
}


//write a configfile (this contains the FED device number)
void FED3::writeConfigFile() {
  digitalWrite (MOTOR_ENABLE, LOW);  //Disable motor driver and neopixel
  configfile = SD.open("DeviceNumber.csv", FILE_WRITE);
  configfile.rewind();
  configfile.println(FED);
  configfile.flush();
  configfile.close();
}

//write a Pelletfile (this contains the Pellet Type Number)
void FED3::writePelletFile() {
  digitalWrite (MOTOR_ENABLE, LOW);  //Disable motor driver and neopixel
  Pelletfile = SD.open("Pelletfile.csv", FILE_WRITE);
  Pelletfile.rewind();
  Pelletfile.println(PelletType);
  Pelletfile.flush();
  Pelletfile.close();
}

void FED3::logdata() {
    if (stopLogging == true) {
        return;
    }
    if (EnableSleep == true) {
        digitalWrite(MOTOR_ENABLE, LOW);  // Disable motor driver and neopixel
    }
    SD.begin(cardSelect, SD_SCK_MHZ(4));

    // Fix filename (the .CSV extension can become corrupted) and open file
    filename[19] = '.';
    filename[20] = 'C';
    filename[21] = 'S';
    filename[22] = 'V';
    logfile = SD.open(filename, FILE_WRITE);

    // If FED3 cannot open file put SD card icon on screen 
    display.fillRect(68, 1, 15, 22, WHITE); // Clear a space
    if (!logfile) {
        // Draw SD card icon
        display.drawRect(70, 2, 11, 14, BLACK);
        display.drawRect(69, 6, 2, 10, BLACK);
        display.fillRect(70, 7, 4, 8, WHITE);
        display.drawRect(72, 4, 1, 3, BLACK);
        display.drawRect(74, 4, 1, 3, BLACK);
        display.drawRect(76, 4, 1, 3, BLACK);
        display.drawRect(78, 4, 1, 3, BLACK);
        // Exclamation point
        display.fillRect(72, 6, 6, 16, WHITE);
        display.setCursor(74, 16);
        display.setTextSize(2);
        display.setFont(&Org_01);
        display.print("!");
        display.setFont(&FreeSans9pt7b);
        display.setTextSize(1);
    }

    

    // Prepare data for logging and serial output
    String logData = "";

    /////////////////////////////////
    // Log date and time 
    /////////////////////////////////
    DateTime now = rtc.now();
    logData += String(now.month()) + "/" + String(now.day()) + "/" + String(now.year()) + " ";
    logData += (now.hour() < 10 ? "0" : "") + String(now.hour()) + ":";
    logData += (now.minute() < 10 ? "0" : "") + String(now.minute()) + ":";
    logData += (now.second() < 10 ? "0" : "") + String(now.second()) + ",";

    /////////////////////////////////
    // Log temp and humidity
    /////////////////////////////////
    if (tempSensor == true) {
        sensors_event_t humidity, temp;
        aht.getEvent(&humidity, &temp); // Populate temp and humidity objects with fresh data
        logData += String(temp.temperature) + "," + String(humidity.relative_humidity) + ",";
    }

    /////////////////////////////////
    // Log library version and Sketch identifier text
    /////////////////////////////////
    logData += String(VER) + ",";
    logData += sessiontype + ",";
    logData += String(FED) + ",";

    /////////////////////////////////
    // Log battery voltage
    /////////////////////////////////
    ReadBatteryLevel();
    logData += String(measuredvbat) + ",";

    /////////////////////////////////
    // Log motor turns
    /////////////////////////////////
    if (Event != "Pellet") {
        logData += "NaN,";
    } else {
        logData += String(numMotorTurns + 1) + ",";
    }

    /////////////////////////////////
    // Log FR ratio
    /////////////////////////////////
    logData += String(FR) + ",";

    /////////////////////////////////
    // Log event type (pellet, right, left)
    /////////////////////////////////
    logData += Event + ",";

    /////////////////////////////////
    // Log Active poke side (left, right)
    /////////////////////////////////
    logData += (activePoke == 0 ? String("Right") : String("Left")) + ",";

    /////////////////////////////////
    // Log data (leftCount, RightCount, Pellets)
    /////////////////////////////////
    logData += String(LeftCount) + "," + String(RightCount) + "," + String(PelletCount) + "," + String(BlockPelletCount) + ",";

    /////////////////////////////////
    // Log pellet retrieval interval
    /////////////////////////////////
    if (Event != "Pellet") {
        logData += "NaN,";
    } else if (retInterval < 60000) {
        logData += String(retInterval / 1000.000) + ",";
    } else if (retInterval >= 60000) {
        logData += "Timed_out,";
    } else {
        logData += "Error,";
    }

    /////////////////////////////////
    // Inter-Pellet-Interval
    /////////////////////////////////
    if ((Event != "Pellet") || (PelletCount < 2)) {
        logData += "NaN,";
    } else {
        logData += String(interPelletInterval) + ",";
    }

    /////////////////////////////////
    // Poke duration
    /////////////////////////////////
    if (Event == "Pellet") {
        logData += "NaN";
    } else if ((Event == "Left") || (Event == "LeftShort") || (Event == "LeftWithPellet") || (Event == "LeftinTimeout") || (Event == "LeftDuringDispense")) {
        logData += String(leftInterval / 1000.000);
    } else if ((Event == "Right") || (Event == "RightShort") || (Event == "RightWithPellet") || (Event == "RightinTimeout") || (Event == "RightDuringDispense")) {
        logData += String(rightInterval / 1000.000);
    } else {
        logData += "NaN";
    }


    // Append Bandit-specific fields if relevant
    // if (sessiontype == "Bandit8020" || sessiontype == "DetBandit" || sessiontype == "ProbRev") {
    //   logData += "," + String(pelletsToSwitch);
    //   logData += "," + String(prob_left);
    //   logData += "," + String(prob_right);
    //   // logData += "," + (prob_left > prob_right ? "Left" : "Right");
    //   logData += "," + String(prob_left > prob_right ? "Left" : "Right");

    // }

    if (sessiontype == "Bandit8020" || sessiontype == "DetBandit") {
      // pellet‐based counter
      logData += "," + String(pelletsToSwitch);
      logData += "," + String(prob_left);
      logData += "," + String(prob_right);
      logData += "," + String(prob_left > prob_right ? "Left" : "Right");
    }
    else if (sessiontype == "ProbRev") {
      // trial‐based counter
      logData += "," + String(trialsToSwitch);
      logData += "," + String(prob_left);
      logData += "," + String(prob_right);
      logData += "," + String(activePoke == 1 ? "Left" : "Right");
    }
    else {
      // **PAD** with four empty fields in every non‐bandit mode
      logData += ",,,,";  
    }

    // now *every* logData has exactly 4 extra commas → fixed length
    Serial.println(logData);
    logfile.println(logData);


    /////////////////////////////////
    // Flush and close logfile
    /////////////////////////////////
    Blink(GREEN_LED, 25, 2);
    logfile.flush();
    logfile.close();
}

void FED3::logJamData() {
  Event = "JAM";
  logdata();
}


// If any errors are detected with the SD card upon boot this function
// will blink both LEDs on the Feather M0, turn the NeoPixel into red wipe pattern,
// and display "Check SD Card" on the screen
void FED3::error(uint8_t errno) {
  if (suppressSDerrors == false){
    DisplaySDError();
    while (1) {
      uint8_t i;
      for (i = 0; i < errno; i++) {
        Blink(GREEN_LED, 25, 2);
        colorWipe(strip.Color(5, 0, 0), 25); // RED
      }
      for (i = errno; i < 10; i++) {
        colorWipe(strip.Color(0, 0, 0), 25); // clear
      }
    }
  }
}


// This function creates a unique filename for each file that
// starts with the letters: "FED_" 
// then the date in MMDDYY followed by "_"
// then an incrementing number for each new file created on the same date
void FED3::getFilename(char *filename) {
  DateTime now = rtc.now();
  //PelletType = 1 ;
  filename[3] = FED / 100 + '0';
  filename[4] = FED / 10 + '0';
  filename[5] = FED % 10 + '0';
  filename[7] = now.month() / 10 + '0';
  filename[8] = now.month() % 10 + '0';
  filename[9] = now.day() / 10 + '0';
  filename[10] = now.day() % 10 + '0';
  filename[11] = (now.year() - 2000) / 10 + '0';
  filename[12] = (now.year() - 2000) % 10 + '0';
  filename[17] = FigureToPellet(PelletType)[0];
  filename[18] = FigureToPellet(PelletType)[1];
  filename[19] = '.';
  filename[20] = 'C';
  filename[21] = 'S';
  filename[22] = 'V';
  for (uint8_t i = 0; i < 100; i++) {
    filename[14] = '0' + i / 10;
    filename[15] = '0' + i % 10;

    if (! SD.exists(filename)) {
      break;
    }
  }
  return;
}

/**************************************************************************************************************************************************
                                                                                                     Change device number
**************************************************************************************************************************************************/
// Change device number
void FED3::SetDeviceNumber() {
  // This code is activated when both pokes are pressed simultaneously from the 
  //start screen, allowing the user to set the device # of the FED on the device
  while (SetFED == true) {
    //adjust FED device number
    display.fillRect (0, 0, 200, 80, WHITE);
    display.setCursor(5, 46);
    display.println("Set Device Number");
    display.fillRect (36, 122, 180, 28, WHITE);
    delay (100);
    display.refresh();

    display.setCursor(38, 138);
    if (FED < 100 & FED >= 10) {
      display.print ("0");
    }
    if (FED < 10) {
      display.print ("00");
    }
    display.print (FED);

    delay (100);
    display.refresh();

    if (digitalRead(RIGHT_POKE) == LOW) {
      FED += 1;
      Click();
      EndTime = millis();
      if (FED > 700) {
        FED = 700;
      }
    }

    if (digitalRead(LEFT_POKE) == LOW) {
      FED -= 1;
      Click();
      EndTime = millis();
      if (FED < 1) {
        FED = 0;
      }
    }
    if (millis() - EndTime > 3000) {  // if 3 seconds passes confirm device #
      SetFED = false;
      display.setCursor(5, 70);
      display.println("...Set!");
      display.refresh();
      delay (1000);
      EndTime = millis();
      display.clearDisplay();
      display.refresh();
            
      ///////////////////////////////////
      //////////  ADJUST CLOCK //////////
      while (millis() - EndTime < 3000) { 
        SetClock();
        delay (10);
      }

      display.setCursor(5, 105);
      display.println("...Clock is set!");
      display.refresh();
      delay (1000);
      display.clearDisplay();
      display.refresh();

      ///////////////////////////////////
      EndTime = millis(); // Needed to make the all thing work !! wasnt here so older endtime was taken in count and the function was skipped 
      while (setTimed == true) {
        // set timed feeding start and stop
        display.fillRect (5, 56, 120, 18, WHITE);
        delay (100);
        display.refresh();

        display.fillRect (0, 0, 200, 80, WHITE);
        display.setCursor(5, 46);
        display.println("Set Timed Feeding");
        display.setCursor(15, 70);
        display.print(timedStart);
        display.print(":00 - ");
        display.print(timedEnd);
        display.print(":00");
        delay (100);
        display.refresh();

        if (digitalRead(LEFT_POKE) == LOW) {
          timedStart += 1;
          EndTime = millis();
          if (timedStart > 24) {
            timedStart = 0;
          }
          if (timedStart > timedEnd) {
            timedEnd = timedStart + 1;
          }
        }

        if (digitalRead(RIGHT_POKE) == LOW) {
          timedEnd += 1;
          EndTime = millis();
          if (timedEnd > 24) {
            timedEnd = 0;
          }
          if (timedStart > timedEnd) {
            timedStart = timedEnd - 1;
          }
        }
        if (millis() - EndTime > 3000) {  // if 3 seconds passes confirm time settings
          setTimed = false;
          display.setCursor(5, 95);
          display.println("...Timing set!");
          display.refresh();
          delay (1000);
          display.clearDisplay();
          display.refresh();  
          
        }
      }
      
      ///////////////////////////////////
      ///////  ADJUST PELLET TYPE ///////
      
      EndTime = millis();
      while (SetPel == true) {
        //adjust PelletType
        display.fillRect (0, 0, 200, 80, WHITE);
        display.setCursor(5, 46);
        display.println("Set PelletType");
        display.fillRect (36, 122, 180, 28, WHITE);
        delay (100);
        display.refresh();

        display.setCursor(6, 75);
        display.print (FigureToPellet(PelletType));
        delay (100);
        display.refresh();
        //PelletType = 1;
        if (digitalRead(RIGHT_POKE) == LOW) {
          PelletType += 1;
          Click();
          EndTime = millis();
          if (PelletType > 7) {
            PelletType = 1;
          }
        }
        if (digitalRead(LEFT_POKE) == LOW) {
          PelletType -= 1;
          Click();
          EndTime = millis();
          if (PelletType < 1) {
            PelletType = 7;
          };
        }
        if (millis() - EndTime > 3000) {  // if 3 seconds passes confirm time settings
          SetPel = false;
          display.setCursor(5, 105);
          display.println("... set!");
          display.refresh();
          delay (1000);
          EndTime = millis();
          display.clearDisplay();
          display.refresh();

          
        }
      }
      writeFEDmode();
      writeConfigFile();
      writePelletFile();
      NVIC_SystemReset();
    }
  }
}

//Convert the Pellet Type number into a two characters code
String FED3::FigureToPellet(int a){
  if (a==1) {
    return ("MX");
  }
  if (a==2) {
    return ("20");
  }
  if (a==3) {
    return ("5%");
  }
  if (a==4) {
    return ("35");
  }
  if (a==5) {
    return ("SU");
  }
  if (a==6) {
    return ("GR");
  }
  else {
    return ("__");//if a==7
  }
}

//set clock
void FED3::SetClock(){
 
  DateTime now = rtc.now();
  unixtime = now.unixtime();

  /********************************************************
       Display date and time of RTC
     ********************************************************/
  display.setCursor(1, 40);
  display.print ("RTC set to:");
  display.setCursor(1, 40);
  display.print ("RTC set to:");

  display.fillRoundRect (0, 45, 400, 25, 1, WHITE);
  //display.refresh();
  display.setCursor(1, 60);
  if (now.month() < 10)
    display.print('0');      // Trick to add leading zero for formatting
  display.print(now.month(), DEC);
  display.print("/");
  if (now.day() < 10)
    display.print('0');      // Trick to add leading zero for formatting
  display.print(now.day(), DEC);
  display.print("/");
  display.print(now.year(), DEC);
  display.print(" ");
  display.print(now.hour(), DEC);
  display.print(":");
  if (now.minute() < 10)
    display.print('0');      // Trick to add leading zero for formatting
  display.print(now.minute(), DEC);
  display.print(":");
  if (now.second() < 10)
    display.print('0');      // Trick to add leading zero for formatting
  display.println(now.second(), DEC);
  display.drawFastHLine(30, 80, 100, BLACK);
  display.refresh();

  if (digitalRead(LEFT_POKE) == LOW) {
    tone (BUZZER, 800, 1);
    rtc.adjust(DateTime(unixtime - 60));
    EndTime = millis();
  }
  
  if (digitalRead(RIGHT_POKE) == LOW) {
    tone (BUZZER, 800, 1);
    rtc.adjust(DateTime(unixtime + 60));
    EndTime = millis();
  }
}

//Read battery level
void FED3::ReadBatteryLevel() {
  analogReadResolution(10);
  measuredvbat = analogRead(VBATPIN);
  measuredvbat *= 2;    // we divided by 2, so multiply back
  measuredvbat *= 3.3;  // Multiply by 3.3V, our reference voltage
  measuredvbat /= 1024; // convert to voltage
}

/**************************************************************************************************************************************************
                                                                                                     Interrupts and sleep
**************************************************************************************************************************************************/

void FED3::disableSleep(){
  EnableSleep = false;                             
}

void FED3::enableSleep(){
  EnableSleep = true;                             
}

//What happens when pellet is detected
void FED3::pelletTrigger() {
  if (digitalRead(PELLET_WELL) == HIGH) {
    PelletAvailable = false;
  }
}

//What happens when left poke is poked
void FED3::leftTrigger() {
  if (digitalRead(PELLET_WELL) == HIGH){
    if (digitalRead(LEFT_POKE) == LOW ) {
      Left = true;
    }
  }
}

//What happens when right poke is poked
void FED3::rightTrigger() {
  if (digitalRead(PELLET_WELL) == HIGH){
    if (digitalRead(RIGHT_POKE) == LOW ) {
      Right = true;
    }
  }
}

//Sleep function
void FED3::goToSleep() {
  if (EnableSleep==true){
    ReleaseMotor();
    delay (2); //let things settle
    LowPower.sleep(5000);  //Wake up every 5 sec to check the pellet well
  }
  pelletTrigger();       //check pellet well to make sure it's not stuck thinking there's a pellet when there's not
}

//Pull all motor pins low to de-energize stepper and save power, also disable motor driver with the EN pin
void FED3::ReleaseMotor () {
  digitalWrite(A2, LOW);
  digitalWrite(A3, LOW);
  digitalWrite(A4, LOW);
  digitalWrite(A5, LOW);
  if (EnableSleep==true){
    digitalWrite(MOTOR_ENABLE, LOW);  //disable motor driver and neopixels
  }
}

/**************************************************************************************************************************************************
                                                                                                     Startup Functions
**************************************************************************************************************************************************/
//Import Sketch variable from the Arduino script
FED3::FED3(String sketch) {
  sessiontype = sketch;
}

//  dateTime function
void dateTime(uint16_t* date, uint16_t* time) {
  DateTime now = rtc.now();
  // return date using FAT_DATE macro to format fields
  *date = FAT_DATE(now.year(), now.month(), now.day());

  // return time using FAT_TIME macro to format fields
  *time = FAT_TIME(now.hour(), now.minute(), now.second());
}
void FED3::begin() {
  Serial.begin(115200);
  // Initialize pins
  pinMode(PELLET_WELL, INPUT);
  pinMode(LEFT_POKE, INPUT);
  pinMode(RIGHT_POKE, INPUT);
  pinMode(VBATPIN, INPUT);
  pinMode(MOTOR_ENABLE, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(A2, OUTPUT);
  pinMode(A3, OUTPUT);
  pinMode(A4, OUTPUT);
  pinMode(A5, OUTPUT);
  pinMode(BNC_OUT, OUTPUT);

  // Initialize RTC
  rtc.begin();

  // Initialize Neopixels
  strip.begin();
  strip.show(); // Initialize all pixels to 'off'

  // Initialize stepper
  stepper.setSpeed(250);

  // Initialize display
  display.begin();
  const int minorHalfSize = min(display.width(), display.height()) / 2;
  display.setFont(&FreeSans9pt7b);
  display.setRotation(3);
  display.setTextColor(BLACK);
  display.setTextSize(1);
 
  //Is AHT20 temp humidity sensor present?
  if (aht.begin()) {
    tempSensor = true;
  }
 
  // Initialize SD card and create the datafile
  SdFile::dateTimeCallback(dateTime);
  CreateFile();

  // Initialize interrupts
  pointerToFED3 = this;
  LowPower.attachInterruptWakeup(digitalPinToInterrupt(PELLET_WELL), outsidePelletTriggerHandler, CHANGE);
  LowPower.attachInterruptWakeup(digitalPinToInterrupt(LEFT_POKE), outsideLeftTriggerHandler, CHANGE);
  LowPower.attachInterruptWakeup(digitalPinToInterrupt(RIGHT_POKE), outsideRightTriggerHandler, CHANGE);

  // Create data file for current session
  CreateDataFile();
  writeHeader();
  EndTime = 0;

  //reset flags
  stopLogging = false;
  jamOccurred = false;
  
  
  // Disable sleep mode to keep the USB Serial connection active
  disableSleep();
  
  //read battery level
  ReadBatteryLevel();
  
  // Startup display uses StartScreen() unless ClassicFED3==true, then use ClassicMenu()
  if (ClassicFED3 == true){
    ClassicMenu();
  }
  if (FED3Menu == true){
    FED3MenuScreen();
  }
  else {
    StartScreen();
  }
  display.clearDisplay();
  display.refresh();
}


void FED3::FED3MenuScreen() {
  display.clearDisplay();
  display.setCursor(1, 135);
  display.print(filename);
  display.setCursor(10, 20); display.println("FED3 Menu");
  display.setCursor(11, 20); display.println("FED3 Menu");
  display.fillRect(0, 30, 160, 80, WHITE);
  display.setCursor(10, 40);
  display.print("Select Mode:");
  
  display.setCursor(10, 60);
  //Text to display selected FR ratio
  if (FEDmode == 0) display.print("Mode 1");
  if (FEDmode == 1) display.print("Mode 2");
  if (FEDmode == 2) display.print("Mode 3");
  if (FEDmode == 3) display.print("Mode 4");
  if (FEDmode == 4) display.print("Mode 5");
  if (FEDmode == 5) display.print("Mode 6");
  if (FEDmode == 6) display.print("Mode 7");
  if (FEDmode == 7) display.print("Mode 8");
  if (FEDmode == 8) display.print("Mode 9");
  if (FEDmode == 9) display.print("Mode 10");
  if (FEDmode == 10) display.print("Mode 11");
  if (FEDmode == 11) display.print("Mode 12");
  if (FEDmode == 12) display.print("Mode 13");
  if (FEDmode == 13) display.print("Mode 14");
  if (FEDmode == 14) display.print("Mode 15");
  if (FEDmode == 15) display.print("Mode 16");
  DisplayMouse();
  display.clearDisplay();
  display.refresh();
}

// Set FEDMode
void FED3::SelectMode() {
  // Mode select on startup screen
  //If both pokes are activated
  if ((digitalRead(LEFT_POKE) == LOW) && (digitalRead(RIGHT_POKE) == LOW)) {
    tone (BUZZER, 3000, 500);
    colorWipe(strip.Color(2, 2, 2), 40); // Color wipe
    colorWipe(strip.Color(0, 0, 0), 20); // OFF
    EndTime = millis();
    SetFED = true;
    setTimed = true;
    SetPel = true;
    SetDeviceNumber();
  }

  //If Left Poke is activated
  else if (digitalRead(LEFT_POKE) == LOW) {
    EndTime = millis();
    FEDmode -= 1;
    tone (BUZZER, 2500, 200);
    colorWipe(strip.Color(2, 0, 2), 40); // Color wipe
    colorWipe(strip.Color(0, 0, 0), 20); // OFF
    if (FEDmode == -1) FEDmode = 15;
  }

  //If Right Poke is activated
  else if (digitalRead(RIGHT_POKE) == LOW) {
    EndTime = millis();
    FEDmode += 1;
    tone (BUZZER, 2500, 200);
    colorWipe(strip.Color(2, 2, 0), 40); // Color wipe
    colorWipe(strip.Color(0, 0, 0), 20); // OFF
    if (FEDmode == 16) FEDmode = 0;
  }

  if (FEDmode < 0) FEDmode = 0;
  if (FEDmode > 15) FEDmode = 15;

  display.fillRect (10, 48, 200, 50, WHITE);  //erase the selected program text
  display.setCursor(10, 60);  //Display selected program

  //In classic mode we pre-specify these programs names
  if (ClassicFED3==true){
    if (FEDmode == 0) display.print("Free feeding");
    if (FEDmode == 1) display.print("FR1");
    if (FEDmode == 2) display.print("FR3");
    if (FEDmode == 3) display.print("FR5");
    if (FEDmode == 4) display.print("Progressive Ratio");
    if (FEDmode == 5) display.print("Extinction");
    if (FEDmode == 6) display.print("Light tracking");
    if (FEDmode == 7) display.print("FR1 (Reversed)");
    if (FEDmode == 8) display.print("Prog Ratio (Rev)");
    if (FEDmode == 9) display.print("Self-Stim");
    if (FEDmode == 10) display.print("Self-Stim (Rev)");
    if (FEDmode == 11) display.print("Timed feeding");
    if (FEDmode == 12) display.print("ClosedEconomy_PR2");
    if (FEDmode == 13) display.print("Probabilistic Reversal");
    if (FEDmode == 14) display.print("Bandit8020");
    if (FEDmode == 15) display.print("DetBandit");

    
    display.refresh();
  }
  
  //Otherwise we don't know them and just use Mode 1 through Mode 4
  else{
    if (FEDmode == 0) display.print("Mode 1");
    if (FEDmode == 1) display.print("Mode 2");
    if (FEDmode == 2) display.print("Mode 3");
    if (FEDmode == 3) display.print("Mode 4");
    if (FEDmode == 4) display.print("Mode 5");
    if (FEDmode == 5) display.print("Mode 6");
    if (FEDmode == 6) display.print("Mode 7");
    if (FEDmode == 7) display.print("Mode 8");
    if (FEDmode == 8) display.print("Mode 9");
    if (FEDmode == 9) display.print("Mode 10");
    if (FEDmode == 10) display.print("Mode 11");
    if (FEDmode == 11) display.print("Mode 12");
    if (FEDmode == 12) display.print("Mode 13");
    if (FEDmode == 13) display.print("Mode 14");
    if (FEDmode == 14) display.print("Mode 15");
    if (FEDmode == 15) display.print("Mode 16");

    display.refresh();
  }
  
  while (millis() - EndTime < 1500) {
    SelectMode();
  }
  display.setCursor(10, 100);
  display.println("...Selected!");
  display.refresh();
  delay (500);
  writeFEDmode();
  delay (200);
  NVIC_SystemReset();      // processor software reset
}

/******************************************************************************************************************************************************
                                                                                               Classic FED3 functions
******************************************************************************************************************************************************/

//  Classic menu display
void FED3::ClassicMenu () {
  //  0 Free feeding
  //  1 FR1
  //  2 FR3
  //  3 FR5
  //  4 Progressive Ratio
  //  5 Extinction
  //  6 Light tracking FR1 task
  //  7 FR1 (reversed)
  //  8 PR (reversed)
  //  9 self-stim
  //  10 self-stim (reversed)
  //  11 time feeding
  //  12 ClosedEconomy_PR1

  // Set FR based on FEDmode
  if (FEDmode == 0) FR = 0;  // free feeding
  if (FEDmode == 1) FR = 1;  // FR1 spatial tracking task
  if (FEDmode == 2) FR = 3;  // FR3
  if (FEDmode == 3) FR = 5; // FR5
  if (FEDmode == 4) FR = 99;  // Progressive Ratio
  if (FEDmode == 5) { // Extinction
    FR = 1;
    ReleaseMotor ();
    digitalWrite (MOTOR_ENABLE, LOW);  //disable motor driver and neopixels
    delay(2); //let things settle
  }
  if (FEDmode == 6) FR = 1;  // Light tracking
  if (FEDmode == 7) FR = 1; // FR1 (reversed)
  if (FEDmode == 8) FR = 1; // PR (reversed)
  if (FEDmode == 9) FR = 1; // self-stim
  if (FEDmode == 10) FR = 1; // self-stim (reversed)
  if (FEDmode == 11) FR = 1; // Timed feeding
  if (FEDmode == 12) FR = 1; // ClosedEconomy_PR1
  if (FEDmode == 13) FR = 1; // Probabilistic Reversal
  if (FEDmode == 14) FR = 1; // Bandit Task
  if (FEDmode == 15) FR = 1; // Deterministic Bandit


  display.clearDisplay();
  display.setCursor(1, 135);
  display.print(filename);

  display.fillRect(0, 30, 160, 80, WHITE);
  display.setCursor(10, 40);
  display.print("Select Program:");
  
  display.setCursor(10, 60);
  //Text to display selected FR ratio
  if (FEDmode == 0) display.print("Free feeding");
  if (FEDmode == 1) display.print("FR1");
  if (FEDmode == 2) display.print("FR3");
  if (FEDmode == 3) display.print("FR5");
  if (FEDmode == 4) display.print("Progressive Ratio");
  if (FEDmode == 5) display.print("Extinction");
  if (FEDmode == 6) display.print("Light tracking");
  if (FEDmode == 7) display.print("FR1 (Reversed)");
  if (FEDmode == 8) display.print("Prog Ratio (Rev)");
  if (FEDmode == 9) display.print("Self-Stim");
  if (FEDmode == 10) display.print("Self-Stim (Rev)");
  if (FEDmode == 11) display.print("Timed feeding");
  if (FEDmode == 12) display.print("ClosedEconomy_PR1");
  if (FEDmode == 13) display.print("Probabilistic Reversal");
  if (FEDmode == 14) display.print("Bandit Task");
  if (FEDmode == 15) display.print("Deterministic Bandit");
  
  DisplayMouse();
  display.clearDisplay();
  display.refresh();
}

//write a FEDmode file (this contains the last used FEDmode)
void FED3::writeFEDmode() {
  ratiofile = SD.open("FEDmode.csv", FILE_WRITE);
  ratiofile.rewind();
  ratiofile.println(FEDmode);
  ratiofile.flush();
  ratiofile.close();

  startfile = SD.open("start.csv", FILE_WRITE);
  startfile.rewind();
  startfile.println(timedStart);
  startfile.flush();
  startfile.close();

  stopfile = SD.open("stop.csv", FILE_WRITE);
  stopfile.rewind();
  stopfile.println(timedEnd);
  stopfile.flush();
  stopfile.close();



}
