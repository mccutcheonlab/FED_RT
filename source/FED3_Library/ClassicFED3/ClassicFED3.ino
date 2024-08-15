/*
  Feeding experimentation device 3 (FED3)
  Classic FED3 script
  This script mimicks the classic FED3 menuing system for selecting among the following programs

  // FEDmodes:
  // 0 Free feeding
  // 1 FR1
  // 2 FR3
  // 3 FR5
  // 4 Progressive Ratio
  // 5 Extinction
  // 6 Light tracking FR1 task
  // 7 FR1 (reversed)
  // 8 PR (reversed)
  // 9 Optogenetic stimulation
  // 10 Optogenetic stimulation (reversed)
  // 11 Timed free feeding
  // 12 ClosedEconomy_PR1 

  alexxai@wustl.edu
  December, 2020

  This project is released under the terms of the Creative Commons - Attribution - ShareAlike 3.0 license:
  human readable: https://creativecommons.org/licenses/by-sa/3.0/
  legal wording: https://creativecommons.org/licenses/by-sa/3.0/legalcode
  Copyright (c) 2020 Lex Kravitz

*/

#include <FED3.h>                //Include the FED3 library 
String sketch = "Classic";       //Unique identifier text for each sketch
FED3 fed3 (sketch);              //Start the FED3 object

//variables for PR tasks
int poke_num = 0;                                      // this variable is the number of pokes since last pellet
int pokes_required = 1;                                // increase the number of pokes required each time a pellet is received using an exponential equation

//variables added for ClosedEconomy_PR1
int pellets_in_current_block = 0;                      //pellet number in current block
unsigned long poketime = 0;                            //time of poke
int resetInterval = 1800;                              //number of seconds without a poke to reset


void setup() {
  fed3.ClassicFED3 = true;
  fed3.begin();                                        //Setup the FED3 hardware
}

void loop() {
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 0: Free feeding
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 0) {
    fed3.sessiontype = "Free_feed";                     //The text in "sessiontype" will appear on the screen and in the logfile
    fed3.DisplayPokes = false;                          //Turn off poke indicators for free feeding mode
    fed3.UpdateDisplay();                               //Update display for free feeding session to remove poke display (they are on by default)
    fed3.Feed();
    fed3.Timeout(5);                                    //5s timeout
 }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Modes 1-3: Fixed Ratio Programs FR1, FR3, FR5
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  if ((fed3.FEDmode == 1) or (fed3.FEDmode == 2) or (fed3.FEDmode == 3)) {
    if (fed3.FEDmode == 1) fed3.sessiontype = "FR1";    //The text in "sessiontype" will appear on the screen and in the logfile
    if (fed3.FEDmode == 2) fed3.sessiontype = "FR3";    //The text in "sessiontype" will appear on the screen and in the logfile
    if (fed3.FEDmode == 3) fed3.sessiontype = "FR5";    //The text in "sessiontype" will appear on the screen and in the logfile
    if (fed3.Left) {
      fed3.logLeftPoke();                               //Log left poke
      if (fed3.LeftCount % fed3.FR == 0) {              //if fixed ratio is  met
        fed3.ConditionedStimulus();                     //deliver conditioned stimulus (tone and lights)
        fed3.Feed();                                    //deliver pellet
      }
    }
    if (fed3.Right) {                                    //If right poke is triggered
      fed3.logRightPoke();
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 4: Progressive Ratio
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 4) {
    fed3.sessiontype = "ProgRatio";                      //The text in "sessiontype" will appear on the screen and in the logfile
    if (fed3.Left) {                                     //If left poke is triggered and pellet is not in the well
      fed3.logLeftPoke();                                //Log left poke
      fed3.Click();                                      //Click
      poke_num++;                                        //store this new poke number as current poke number.
      if (poke_num == pokes_required) {                  //check to see if the mouse has acheived the correct number of pokes in order to receive the pellet
        fed3.ConditionedStimulus();                      //Deliver conditioned stimulus (tone and lights)
        fed3.Feed();                                     //Deliver pellet
        pokes_required = round((5 * exp((fed3.PelletCount + 1) * 0.2)) - 5);  //increment the number of pokes required according to the progressive ratio:
        fed3.FR = pokes_required;
        poke_num = 0;                                    //reset poke_num back to 0 for the next trial
      }
    }
    if (fed3.Right) {                                    //If right poke is triggered and pellet is not in the well
      fed3.logRightPoke();
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 5: Extinction
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 5) {
    fed3.sessiontype = "Extinct";                        //The text in "sessiontype" will appear on the screen and in the logfile
    if (fed3.Left) {
      fed3.logLeftPoke();                                //Log left poke
      fed3.ConditionedStimulus();                        //deliver conditioned stimulus (tone and lights)
    }

    if (fed3.Right) {                                    //If right poke is triggered
      fed3.logRightPoke();
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                    Mode 6: Light tracking FR1 task
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 6) {
    fed3.sessiontype = "Light Trk";                       //The text in "sessiontype" will appear on the screen and in the logfile
    fed3.disableSleep();                                  //Sleep mode shuts the NeoPixels off to save power.  Therefore to leave pixels on during this task we must disable sleep mode.

    //If left poke is active, run FR1 session with left active
    if (fed3.activePoke == 1) {

      //Comment one of these next two lines out, depending on if you have FED3 or FED3.1 (with nosepoke lights)
            fed3.leftPokePixel(5,5,5,0) ;                       //turn on pixel inside left nosepoke dim white
//      fed3.leftPixel(5, 5, 5, 5) ;                       //turn on left-most pixel on Neopixel strip

      if (fed3.Left) {
        fed3.logLeftPoke();                               //Log left poke
        fed3.ConditionedStimulus();                       //deliver conditioned stimulus (tone and lights)
        fed3.Feed();
        fed3.randomizeActivePoke(3);                      //randomize which poke is active, specifying maximum on the same poke before forcing a switch
      }
      if (fed3.Right) {                                   //If right poke is triggered
        fed3.logRightPoke();
      }
    }
    //If right poke is active, run FR1 session with right active
    if (fed3.activePoke == 0) {

      //Comment one of these next two lines out, depending on if you have FED3 or FED3.1 (with nosepoke lights)
            fed3.rightPokePixel(5,5,5,0) ;                    //turn on pixel inside right nosepoke dim white
//      fed3.rightPixel(5, 5, 5, 5) ;                      //turn on right-most pixel on Neopixel strip

      if (fed3.Right) {
        fed3.logRightPoke();                              //Log left poke
        fed3.ConditionedStimulus();                       //deliver conditioned stimulus (tone and lights)
        fed3.Feed();                                      //deliver pellet
        fed3.randomizeActivePoke(3);                      //randomize which poke is active, specifying maximum on the same poke before forcing a switch
      }
      if (fed3.Left) {                                    //If right poke is triggered
        fed3.logLeftPoke();
      }
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 7: FR1 (reversed)
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 7) {
    fed3.sessiontype = "FR1_R";                           //The text in "sessiontype" will appear on the screen and in the logfile
    fed3.activePoke = 0;                                  //Set activePoke to 0 to make right poke active
    if (fed3.Left) {                                      //If left poke
      fed3.logLeftPoke();                                 //Log left poke
    }
    if (fed3.Right) {                                     //If right poke is triggered
      fed3.logRightPoke();                                //Log Right Poke
      fed3.ConditionedStimulus();                         //Deliver conditioned stimulus (tone and lights)
      fed3.Feed();                                        //deliver pellet
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 8: PR (reversed)
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 8) {
    fed3.sessiontype = "PR_R";                          //The text in "sessiontype" will appear on the screen and in the logfile
    fed3.activePoke = 0;                                //Right poke is active
    if (fed3.Right) {                                   //If Right poke is triggered
      fed3.logRightPoke();                              //Log Right poke
      poke_num++;                                       //store this new poke number as current poke number.
      if (poke_num == pokes_required) {                 //check to see if the mouse has acheived the correct number of pokes in order to receive the pellet
        fed3.ConditionedStimulus();                     //Deliver conditioned stimulus (tone and lights)
        fed3.Feed();                                    //Deliver pellet
        //increment the number of pokes required according to the progressive ratio:
        pokes_required = round((5 * exp((fed3.PelletCount + 1) * 0.2)) - 5);
        fed3.FR = pokes_required;
        poke_num = 0;                                   //reset the number of pokes back to 0, for the next trial
        fed3.Right = false;
      }
      else {
        fed3.Click();                                   //If not enough pokes, just do a Click
      }
    }
    if (fed3.Left) {                                    //If left poke is triggered and pellet is not in the well
      fed3.logLeftPoke();
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 9: Optogenetic stimulation
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 9) {
    fed3.sessiontype = "OptoStim";                      //The text in "sessiontype" will appear on the screen and in the logfile
    if (fed3.Left) {                                    //If left poke
      fed3.logLeftPoke();                               //Log left poke
      fed3.ConditionedStimulus();                       //Deliver conditioned stimulus (tone and lights)
      fed3.BNC(25, 20);                                 //Deliver 20 pulses at 20Hz (25ms HIGH, 25ms LOW), lasting 1 second
    }
    if (fed3.Right) {                                   //If right poke is triggered
      fed3.logRightPoke();                              //Log Right Poke
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 10: Optogenetic stimulation (reversed)
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 10) {
    fed3.sessiontype = "OptoStim_R";                     //The text in "sessiontype" will appear on the screen and in the logfile
    fed3.activePoke = 0;                                 //Set activePoke to 0 to make right poke active
    if (fed3.Right) {                                    //If Right poke
      fed3.logRightPoke();                               //Log Right poke
      fed3.ConditionedStimulus();                        //Deliver conditioned stimulus (tone and lights)
      fed3.BNC(25, 20);                                  //Deliver 20 pulses at 20Hz (25ms HIGH, 25ms LOW), lasting 1 second
    }
    if (fed3.Left) {                                     //If Left poke is triggered
      fed3.logLeftPoke();                                //Log LeftPoke
    }
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 11: Timed Feeding
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  if (fed3.FEDmode == 11) {
    fed3.sessiontype = "Timed";                         //The text in "sessiontype" will appear on the screen and in the logfile
    fed3.DisplayPokes = false;                          //Turn off poke indicators for free feeding mode
    fed3.DisplayTimed = true;                           //Display timed feeding info
    fed3.UpdateDisplay();
    if (fed3.currentHour >= fed3.timedStart && fed3.currentHour < fed3.timedEnd) {
      fed3.Feed();
      fed3.Timeout(5);                                  //5s timeout
    }
  }



  ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                     Mode 12: Test addition of ClosedEconomy_PR1 (another program) as part of this program 
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  if (fed3.FEDmode == 12) {
    fed3.sessiontype = "ClEco_PR1";                       //The text in "sessiontype" will appear on the screen and in the logfile
      checkReset();                                        //Check if it's time to reset to FR1
      if (fed3.Left) {                                     //If left poke is triggered
        fed3.logLeftPoke();                                //log Left poke
        poke_num++;                                        //increment poke number.
        poketime = fed3.unixtime;                          //update the current time of poke
        serialoutput();                                    //print data to the Serial monitor - EnableSleep must be false to use Serial monitor
        if (poke_num == pokes_required) {                  //check if current FR has been achieved
          fed3.ConditionedStimulus();                      //Deliver conditioned stimulus (tone and lights)
          pellets_in_current_block++;                      //increment the pellet number by 1
          fed3.BlockPelletCount = pellets_in_current_block;
          fed3.Feed();                                     //Deliver pellet
          //fed3.BNC(500, 1);                                //Send 500ms pulse to the BNC output when pellet is detected (move this line to deliver this pulse elsewhere)
          pokes_required += 2;                             //Edit this line to change the PR incremementing formula.  Default is for each pellet add 1 to the pokes required.
          fed3.FR = pokes_required;                        //Update the FR requirement in the functions in the FED3 library
          poke_num = 0;                                    //reset poke_num to 0
        }
      }

      if (fed3.Right) {                                    //If right poke is triggered
        fed3.logRightPoke();                               //log right poke
      }
    }

  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  //                                                                    Call fed.run at least once per loop
  ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  fed3.run();

}

//////////////////////////////////////////////////////////////////////////////////////
//if more than 30 mins has passed since last poke -- reset the block and parameters
//////////////////////////////////////////////////////////////////////////////////////
void checkReset() {
  if (fed3.unixtime - poketime >= resetInterval) {   //if the reset interval has elapsed since last poke
    pellets_in_current_block = 0;
    fed3.BlockPelletCount = pellets_in_current_block;
    poke_num = 0;
    pokes_required = 1;
    fed3.FR = pokes_required;
    Serial.println("          ");
    Serial.println("****");                           //print **** on the serial monitor

    fed3.pixelsOn(5, 5, 5, 5);
    delay(200);
    fed3.pixelsOff();
    poketime = fed3.unixtime;                        //store the current time of poke
  }
}

//////////////////////////////////////////////////////////////////////////////////////
// Use Serial.print statements for debugging
//////////////////////////////////////////////////////////////////////////////////////
void serialoutput() {
  Serial.print("Unixtime: ");
  Serial.println(fed3.unixtime);
  Serial.println("Pellets   RightPokes   LeftPokes   Poke_Num  Pel  Pokes_Required  PokeTime   Reset  FR");
  Serial.print("   ");
  Serial.print(fed3.PelletCount);
  Serial.print("          ");
  Serial.print(fed3.RightCount);
  Serial.print("          ");
  Serial.print(fed3.LeftCount);
  Serial.print("          ");
  Serial.print(poke_num);
  Serial.print("          ");
  Serial.print(pellets_in_current_block);
  Serial.print("          ");
  Serial.print(pokes_required);
  Serial.print("       ");
  Serial.print(poketime);
  Serial.print("          ");
  Serial.print(fed3.FR);
  Serial.println(" ");
  Serial.println(" ");

}
