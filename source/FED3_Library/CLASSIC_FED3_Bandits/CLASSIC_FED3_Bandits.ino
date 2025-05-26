/*
  Adding Modes 0–15 (Classic + ProbRev + Bandit + Deterministic Bandit) to FED3 edited May 23 2025 by Hamid Taghipourbibalan
*/

#include <FED3.h>
String sketch = "Classic_with_ProbRev";
FED3 fed3(sketch);

// Variables for PR tasks (mode 4, 8, 12)
int poke_num = 0;
int pokes_required = 1;
int pellets_in_current_block = 0;
unsigned long poketime = 0;
int resetInterval = 1800; // seconds without a poke to reset (for mode 12)

// Variables for Mode 13: Probabilistic Reversal Task
int probability = 80;
int trialsToSwitch = 10;
int counter = 1;
int trialTimeout = 5;

// Variables for Mode 14: Bandit Task
int pellet_counter = 0;
int timeoutIncorrect = 10;
int probs[2] = {80, 20};
int new_prob = 0;

// Variables for Mode 15: Deterministic Bandit Task
int pellet_counter_det = 0;
int deterministicPelletsToSwitch = 20; //////////////////////////////////////////REMEMBER TO CHANGE TO 20///////////////////////////////////////////
bool rewardLeft = true;
/////////////////////////////in case we want to have different probs in Bandit8020 task we can do the followings #############1################////////////////////////////////////////////////////////
////////////////////////// Maybe add these variables here before the void setup() 
// ——— Multi-probability Bandit settings ———
// How many pellets before we switch probability
//const int pelletsToSwitch = 5;
//
//// List of {left%, right%} pairs to cycle through (or pick at random)
//const int probabilitySets[][2] = {
//  {80, 20},
//  {70, 30},
//  {60, 40},
//  {90, 10},
//  {50, 50}
//};
//const int numSets = sizeof(probabilitySets) / sizeof(probabilitySets[0]);
//
//int currentSet    = 0;  // index into probabilitySets
//int pelletCounter = 0;  // counts rewarded pellets in current block

/////////////////////////////////////////###########################2#################################//////////////////////////
//void setup() {
//  // 1) Seed the random number generator
//  randomSeed( analogRead(A0) );
//
//  // 2) Usual FED3 init
//  fed3.ClassicFED3 = true;
//  fed3.begin();
//
//  // 3) If we boot in Mode 14, load the first probability set:
//  if (fed3.FEDmode == 14) {
//    fed3.prob_left  = probabilitySets[currentSet][0];
//    fed3.prob_right = probabilitySets[currentSet][1];
//  }
//}


////////////////////////////////////and then replace the mode 14 with the code below //////////////////////////////////
/////////////////////////////////////////////////////////##########################3##################################//////////////////////////

//// Mode 14: Bandit with multiple probability blocks
//else if (fed3.FEDmode == 14) {
//  fed3.sessiontype = "Bandit8020";
//
//  // — LEFT poke —
//  if (fed3.Left) {
//    fed3.logLeftPoke();
//    if (random(100) < fed3.prob_left) {
//      fed3.ConditionedStimulus();
//      fed3.Feed();
//      pelletCounter++;
//
//      // check & switch immediately
//      if (pelletCounter >= pelletsToSwitch) {
//        pelletCounter = 0;
//        // either cycle:
//        currentSet = (currentSet + 1) % numSets;
//        // or choose randomly:
//        // currentSet = random(numSets);
//
//        // load new probs
//        fed3.prob_left  = probabilitySets[currentSet][0];
//        fed3.prob_right = probabilitySets[currentSet][1];
//
//        Serial.print("Switched to P(L)=");
//        Serial.print(fed3.prob_left);
//        Serial.print("/P(R)=");
//        Serial.println(fed3.prob_right);
//      }
//    } else {
//      fed3.Click();
//    }
//    fed3.BlockPelletCount = pelletCounter;
//  }
//
//  // — RIGHT poke —
//  if (fed3.Right) {
//    fed3.logRightPoke();
//    if (random(100) < fed3.prob_right) {
//      fed3.ConditionedStimulus();
//      fed3.Feed();
//      pelletCounter++;
//
//      // same switch logic
//      if (pelletCounter >= pelletsToSwitch) {
//        pelletCounter = 0;
//        currentSet = (currentSet + 1) % numSets;
//        // or: currentSet = random(numSets);
//
//        fed3.prob_left  = probabilitySets[currentSet][0];
//        fed3.prob_right = probabilitySets[currentSet][1];
//
//        Serial.print("Switched to P(L)=");
//        Serial.print(fed3.prob_left);
//        Serial.print("/P(R)=");
//        Serial.println(fed3.prob_right);
//      }
//    } else {
//      fed3.Click();
//    }
//    fed3.BlockPelletCount = pelletCounter;
//  }
//}

//////////////////////////
void setup() {
  randomSeed( analogRead(A0) );
  fed3.ClassicFED3 = true;
  fed3.begin();
  fed3.trialsToSwitch = trialsToSwitch;
  if (fed3.FEDmode == 14) {
    fed3.prob_left  = probs[0];  // 80%
    fed3.prob_right = probs[1];  // 20%
  }
}

void loop() {
  // Mode 0: Free feed
  if (fed3.FEDmode == 0) {
    fed3.sessiontype = "Free_feed";
    fed3.DisplayPokes = false;
    fed3.UpdateDisplay();
    fed3.Feed();
    fed3.Timeout(5);
  }
  // Modes 1–3: FR1, FR3, FR5
  else if (fed3.FEDmode == 1 || fed3.FEDmode == 2 || fed3.FEDmode == 3) {
    if (fed3.FEDmode == 1)   fed3.sessiontype = "FR1";
    else if (fed3.FEDmode == 2) fed3.sessiontype = "FR3";
    else                      fed3.sessiontype = "FR5";
    if (fed3.Left) {
      fed3.logLeftPoke();
      if (fed3.LeftCount % fed3.FR == 0) {
        fed3.ConditionedStimulus();
        fed3.Feed();
      }
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 4: Progressive Ratio
  else if (fed3.FEDmode == 4) {
    fed3.sessiontype = "ProgRatio";
    if (fed3.Left) {
      fed3.logLeftPoke();
      fed3.Click();
      poke_num++;
      if (poke_num == pokes_required) {
        fed3.ConditionedStimulus();
        fed3.Feed();
        pokes_required = round((5 * exp((fed3.PelletCount + 1) * 0.2)) - 5);
        fed3.FR = pokes_required;
        poke_num = 0;
      }
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 5: Extinction
  else if (fed3.FEDmode == 5) {
    fed3.sessiontype = "Extinct";
    if (fed3.Left) {
      fed3.logLeftPoke();
      fed3.ConditionedStimulus();
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 6: Light Tracking
  else if (fed3.FEDmode == 6) {
    fed3.sessiontype = "Light Trk";
    fed3.disableSleep();
    if (fed3.activePoke == 1) {
      fed3.leftPokePixel(5,5,5,0);
      if (fed3.Left) {
        fed3.logLeftPoke();
        fed3.ConditionedStimulus();
        fed3.Feed();
        fed3.randomizeActivePoke(3);
      }
      if (fed3.Right) fed3.logRightPoke();
    } else {
      fed3.rightPokePixel(5,5,5,0);
      if (fed3.Right) {
        fed3.logRightPoke();
        fed3.ConditionedStimulus();
        fed3.Feed();
        fed3.randomizeActivePoke(3);
      }
      if (fed3.Left) fed3.logLeftPoke();
    }
  }
  // Mode 7: FR1, Reversed
  else if (fed3.FEDmode == 7) {
    fed3.sessiontype = "FR1_R";
    fed3.activePoke = 0;
    if (fed3.Left)  fed3.logLeftPoke();
    if (fed3.Right) {
      fed3.logRightPoke();
      fed3.ConditionedStimulus();
      fed3.Feed();
    }
  }
  // Mode 8: Progressive Ratio, Reversed
  else if (fed3.FEDmode == 8) {
    fed3.sessiontype = "PR_R";
    fed3.activePoke = 0;
    if (fed3.Right) {
      fed3.logRightPoke();
      poke_num++;
      if (poke_num == pokes_required) {
        fed3.ConditionedStimulus();
        fed3.Feed();
        pokes_required = round((5 * exp((fed3.PelletCount + 1) * 0.2)) - 5);
        fed3.FR = pokes_required;
        poke_num = 0;
      } else {
        fed3.Click();
      }
    }
    if (fed3.Left) fed3.logLeftPoke();
  }
  // Mode 9: OptoStim
  else if (fed3.FEDmode == 9) {
    fed3.sessiontype = "OptoStim";
    if (fed3.Left) {
      fed3.logLeftPoke();
      fed3.ConditionedStimulus();
      fed3.BNC(25, 20);
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 10: OptoStim, Right only
  else if (fed3.FEDmode == 10) {
    fed3.sessiontype = "OptoStim_R";
    fed3.activePoke = 0;
    if (fed3.Right) {
      fed3.logRightPoke();
      fed3.ConditionedStimulus();
      fed3.BNC(25, 20);
    }
    if (fed3.Left) fed3.logLeftPoke();
  }
  // Mode 11: Timed access
  else if (fed3.FEDmode == 11) {
    fed3.sessiontype = "Timed";
    fed3.DisplayPokes = false;
    fed3.DisplayTimed = true;
    fed3.UpdateDisplay();
    if (fed3.currentHour >= fed3.timedStart && fed3.currentHour < fed3.timedEnd) {
      fed3.Feed();
      fed3.Timeout(5);
    }
  }
  // Mode 12: Closed Economy PR2
  else if (fed3.FEDmode == 12) {
    fed3.sessiontype = "ClEco_PR2";
    checkReset();
    if (fed3.Left) {
      fed3.logLeftPoke();
      poke_num++;
      poketime = fed3.unixtime;
      serialoutput();
      if (poke_num == pokes_required) {
        fed3.ConditionedStimulus();
        pellets_in_current_block++;
        fed3.BlockPelletCount = pellets_in_current_block;
        fed3.Feed();
        pokes_required += 2;
        fed3.FR = pokes_required;
        poke_num = 0;
      }
    }
    if (fed3.Right) fed3.logRightPoke();
  }

// Mode 13: Probabilistic Reversal
else if (fed3.FEDmode == 13) {
  fed3.sessiontype = "ProbRev";
  fed3.disableSleep();

  // Which half of the block are we in?
  // counter runs 1…(2*trialsToSwitch), then wraps.
  bool highLeft = (counter <= trialsToSwitch);

  // Tell the display/log which side is “high-prob”
  fed3.prob_left  = highLeft ? probability : (100 - probability);
  fed3.prob_right = highLeft ? (100 - probability) : probability;
  fed3.activePoke = highLeft ? 1 : 0;

  //  LEFT poke
  if (fed3.Left) {
    fed3.logLeftPoke();
    if (random(100) < fed3.prob_left) {
      fed3.ConditionedStimulus();
      fed3.Feed();
    } else {
      fed3.Click();       // short click instead of buzz
    }
    counter++;
  }

  // RIGHT poke event
  if (fed3.Right) {
    fed3.logRightPoke();
    if (random(100) < fed3.prob_right) {
      fed3.ConditionedStimulus();
      fed3.Feed();
    } else {
      fed3.Click();
    }
    counter++;
  }

  // wrap counter back into 1…2*trialsToSwitch
  if (counter > trialsToSwitch * 2) {
    counter = 1;
  }

  // (optional) show trial-within-block
  fed3.BlockPelletCount = highLeft
    ? (counter - 1)
    : (counter - trialsToSwitch - 1);
}



// Mode 14: Bandit8020 (probabilistic, switch 80/20 every N pellets)
else if (fed3.FEDmode == 14) {
  fed3.sessiontype      = "Bandit8020";
  fed3.pelletsToSwitch  = 20;
  fed3.allowBlockRepeat = false;

  // LEFT poke
  if (fed3.Left) {
    fed3.logLeftPoke();
    if (random(100) < fed3.prob_left) {
      fed3.ConditionedStimulus();
      fed3.Feed();
      pellet_counter++;
      // immediate swap check
      if (pellet_counter >= fed3.pelletsToSwitch) {
        pellet_counter = 0;
        int tmp = fed3.prob_left;
        fed3.prob_left  = fed3.prob_right;
        fed3.prob_right = tmp;
        Serial.println(">> Bandit probs swapped: L=" 
                        + String(fed3.prob_left)
                        + "  R=" + String(fed3.prob_right));
      }
    } else {
      fed3.Click();
    }
    fed3.BlockPelletCount = pellet_counter;
  }

  // RIGHT poke
  if (fed3.Right) {
    fed3.logRightPoke();
    if (random(100) < fed3.prob_right) {
      fed3.ConditionedStimulus();
      fed3.Feed();
      pellet_counter++;
      // immediate swap check
      if (pellet_counter >= fed3.pelletsToSwitch) {
        pellet_counter = 0;
        int tmp = fed3.prob_left;
        fed3.prob_left  = fed3.prob_right;
        fed3.prob_right = tmp;
        Serial.println(">> Bandit probs swapped: L=" 
                        + String(fed3.prob_left)
                        + "  R=" + String(fed3.prob_right));
      }
    } else {
      fed3.Click();
    }
    fed3.BlockPelletCount = pellet_counter;
  }
}




// Mode 15: Deterministic Bandit (100% vs 0%, switch after fixed pellets)
else if (fed3.FEDmode == 15) {
  fed3.sessiontype = "DetBandit";
  fed3.disableSleep();


  fed3.prob_left  = rewardLeft ? 100 : 0;
  fed3.prob_right = rewardLeft ?   0 : 100;

//  if (pellet_counter_det == deterministicPelletsToSwitch) {
//    pellet_counter_det = 0;
//    rewardLeft = !rewardLeft;
//  }
  if (pellet_counter_det == deterministicPelletsToSwitch) {
    pellet_counter_det = 0;
    rewardLeft = !rewardLeft;
  
    fed3.prob_left = rewardLeft ? 100 : 0;
    fed3.prob_right = rewardLeft ? 0 : 100;
  }


  if (fed3.Left) {
    fed3.BlockPelletCount = pellet_counter_det;
    fed3.logLeftPoke();
    if (rewardLeft) {
      fed3.ConditionedStimulus(); fed3.Feed();
      pellet_counter_det++;
    } else {
      fed3.Click();
    }
  }

  if (fed3.Right) {
    fed3.BlockPelletCount = pellet_counter_det;
    fed3.logRightPoke();
    if (!rewardLeft) {
      fed3.ConditionedStimulus(); fed3.Feed();
      pellet_counter_det++;
    } else {
      fed3.Click();
    }
  }
}


  fed3.run();
}

// Helper for mode 12
void checkReset() {
  if (fed3.unixtime - poketime >= resetInterval) {
    pellets_in_current_block = 0;
    fed3.BlockPelletCount = pellets_in_current_block;
    poke_num = 0;
    pokes_required = 1;
    fed3.FR = pokes_required;
    Serial.println("\n****");
    fed3.pixelsOn(5, 5, 5, 5);
    delay(200);
    fed3.pixelsOff();
    poketime = fed3.unixtime;
  }
}

// Serial output utility for mode 12
void serialoutput() {
  Serial.print("Unixtime: "); Serial.println(fed3.unixtime);
  Serial.println("Pellets   RightPokes   LeftPokes   Poke_Num  Pel  Pokes_Required  PokeTime   Reset  FR");
  Serial.print("   "); Serial.print(fed3.PelletCount); Serial.print("          ");
  Serial.print(fed3.RightCount);   Serial.print("          ");
  Serial.print(fed3.LeftCount);    Serial.print("          ");
  Serial.print(poke_num);          Serial.print("          ");
  Serial.print(pellets_in_current_block); Serial.print("          ");
  Serial.print(pokes_required);    Serial.print("       ");
  Serial.print(poketime);          Serial.print("          ");
  Serial.print(fed3.FR);           Serial.println("\n");
}
