#!/user/bin/env python3
# exglobal_chem_initialize.py
# This script creates a ChemistryAnalysis class
# and runs the initialize method
# which creates and stages the runtime directory
# and creates the YAML configuration
# for a global chemistry and aerosol forecast system
import os

from wxflow import Logger, cast_strdict_as_dtypedict
from pygfs.task.chem_initialize import ChemistryInit

logger = Logger(level='DEBUG', colored_log=True)

if __name__ == '__main__':

  # Take configuration from environment and cast it as python dictionary
  config = cast_strdict_as_dtypedict(os.environ)

  # Instantiate the chemistry analysis task
  ChemInit = ChemistryInit(config)

  # Initialize GCAFS Chemistry Constituent Analysis
  ChemInit.initialize()