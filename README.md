# How Well Delta Debugging Works in Real-world Fault Localization - A Study on Linux Kernel.

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

## Dataset (./syzbot_data)
The data we use to perform the study.

## Statistics (./analyses)
Before continuing, you should check the paths and database address in config.py

- gt_filter.py

	Filter out the unreasonable fixes tags.

	See details in the code comments.

- ground_truth.py

	Build the ground truth.

	*Note: You can directly load the syzbot_data/syzbot_bug_info.sql into your database, instead of building from scratch.*

------------------------------------------------

- data.py

	Calculate the following statistics:

	1) overall performance;

	2) impact on bug-fixing time;

	3) distribution of result commits

- efficiency_analysis.py

	Calculate the following statistics:

	1) Avg building time and testing time for each commit;

	2) analysis of the tested commits who cost more time than avg time, i.e. expected commits to test VS. actual.

------------------------------------------------

- failure_cause_analysis.py

	Analyze the failure causes (C1/C2/T1/T2/T3)

------------------------------------------------

- dreamutil.py

	Extract the files and functions modified by a commit.

	Only support C/C++.

	Parsing grammar is based on srcml.

- file_maintainer.py

	Obtain the maintainer information of guilty file, and output to maintainers_crash_report.json

- relation_between_two_commits.py

	Examine the relationship between the result commit and patch commit, including the developer assignment and code location (line, func, file), respectively for correct/incorrect bisection result.

------------------------------------------------

- time_limit.py

	Calculate the avg number of versions tested if a timeout occurs.

------------------------------------------------

- dataset_dist.py

	Count the version distribution of ground-truth commit and crash commit.

