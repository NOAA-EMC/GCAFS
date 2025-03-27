#!/usr/bin/env python3

import os

from wxflow import Logger, logit, save_as_yaml, cast_strdict_as_dtypedict
from pygfs.task.gfs_forecast import GFSForecast

# initialize root logger
logger = Logger(level=os.environ.get("LOGGING_LEVEL"), colored_log=True)


@logit(logger)
def main():

    # instantiate the forecast
    config = cast_strdict_as_dtypedict(os.environ)
    # Temporarily save the input to the Forecast
    save_as_yaml(config, f'{config.EXPDIR}/fcst.yaml')

    fcst = GFSForecast(config)
    fcst.initialize()
    fcst.configure()


if __name__ == '__main__':
    main()
