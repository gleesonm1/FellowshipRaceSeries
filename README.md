# Fellowship Race Series

This repository contains the code needed to process zwift racing results and maintain the Fellowship Race Series results page at:

https://fellowshipraceseries.streamlit.app/

## How to use
Feel free to copy the code to design your own app.

If you're looking to use this to process results from a Fellowship series then contact me for access.

The code is hopefully quite simple. In each folder there should be a Python file that can be used to scrape results from Zwift Power. The code extensively uses the fantastic package ZPDataFetch (https://github.com/puckdoug/zpdatafetch). Before starting follow the instructions on the ZPDataFetch page for setting up you Zwift Power authorization (I suggest creating a new Python environment for this work).

Once your Zwift Power authorization has been entered, clone this repository onto your local machine. Using the terminal or command prompt navigate to the relevant folder (e.g., 'FellowshipChampionships') and run the Python script located there. There are two options for running the script. Option one is to simply run the command

```
python FellowshipChampionships.py 
```

This will process the results from ALL races listed in the .py file.
