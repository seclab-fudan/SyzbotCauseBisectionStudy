# How Well Industry-level Cause Bisection Works in Real-world - A Study on Linux Kernel.

## Prerequisites
- python environment
    ```
    conda env create -f syzbot_bisect_env.yaml -n syzbot_bisect
    ```
- srcml

    1. download from https://www.srcml.org/#download
    2. config .bashrc
    ```
        export PATH=/PATH/TO/srcml/bin:$PATH
        export LD_LIBRARY_PATH=/PATH/TO/srcml/lib:$LD_LIBRARY_PATH
	```

- create a MYSQL database using syzbot\_data/syzbot\_bug\_info.sql

- assign the global variables in the analyses/config.py according to your database configuration.
	```
	DATA_DIR = '../syzbot_data'
	DB_IP = '1.1.1.1'
	DB_PORT = 6603
	DB_USER = 'a'
	DB_PWD = 'a'
	DB_NAME = 'a'
	```

## Dataset (./syzbot\_data)
The data we use to perform the study.

## Statistics (./analyses)
Before continuing, you should check the paths and database address in config.py

- gt\_filter.py

	Filter out the unreasonable fixes tags.

	See details in the code comments.

- ground\_truth.py

	Build the ground truth.

	*Note: You can directly load the syzbot_data/syzbot_bug_info.sql into your database, instead of building from scratch.*

- data.py

	Calculate the following statistics:

	1) overall performance;

	2) impact on bug-fixing time;

	3) distribution of result commits

- efficiency\_analysis.py

	Calculate the following statistics:

	1) Avg building time and testing time for each commit;

	2) analysis of the tested commits who cost more time than avg time, i.e. expected commits to test VS. actual.

- failure\_cause\_analysis.py

	Analyze the failure causes (C1/C2/T1/T2/T3)

- dreamutil.py

	Extract the files and functions modified by a commit.

	Only support C/C++.

	Parsing grammar is based on srcml.

- file\_maintainer.py

	Obtain the maintainer information of guilty file, and output to maintainers_crash_report.json

- relation\_between\_two\_commits.py

	Examine the relationship between the result commit and patch commit, including the developer assignment and code location (line, func, file), respectively for correct/incorrect bisection result.

- time\_limit.py

	Calculate the avg number of versions tested if a timeout occurs.

- dataset\_dist.py

	Count the version distribution of ground-truth commit and crash commit.

