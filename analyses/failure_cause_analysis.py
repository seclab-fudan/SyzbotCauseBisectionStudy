import git
from git import GitCommandError
from multiprocessing import Pool
import pandas
import os

from config import DATA_DIR

ERROR_NOT_REPRODUCED = "error: the crash wasn't reproduced on the original commit"
ERROR_TIMEOUT = "error: bisection is taking too long (>8h0m0s), aborting"
BUG_ON_OLD_RELEASE = "the crash already happened on the oldest tested release"

C1 = 'C1'
C2 = 'C2'
T1 = 'T1'
T2 = 'T2'
T3 = 'T3'

LINUX_REPO = git.Repo(os.path.join(DATA_DIR, 'linux-next-history'))


def str2list(str):
    list = []
    if str != '' and str is not None:
        list = str.split(",")
    return list


def get_commit_id(tag):
    return LINUX_REPO.git.rev_list("-n", "1", tag)


def is_ancestor(commit_a, commit_b):
    try:
        LINUX_REPO.git.merge_base("--is-ancestor", commit_a, commit_b)
        return True
    except GitCommandError as err:
        if err.status == 1:
            return False
        raise


def get_test_results_stageB(cause_bisect_log):
    cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % cause_bisect_log)
    good = None
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            line = line.strip().lower()
            if "# git bisect start" in line:
                _, _, good = line.rsplit(maxsplit=2)
                if len(good) != 40:
                    good = get_commit_id(good)
                break

    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        if good is not None:
            end_flag = "testing commit %s" % good
        else:
            end_flag = "revisions tested:"

        result_dict = dict()
        test_release_flag = False
        wait_for_result = None
        for line in f.readlines():
            line = line.strip().lower()
            if "testing release" in line:
                test_release_flag = True
                if wait_for_result is not None:
                    result_dict[wait_for_result] = "skip"
                    wait_for_result = None
            elif end_flag in line:
                if wait_for_result is not None:
                    result_dict[wait_for_result] = "skip"

                if good is not None:
                    result_dict[good] = "good"
                return result_dict
            elif test_release_flag and "testing commit" in line:
                wait_for_result = line.split()[2]
            elif wait_for_result is not None:
                if ("run #" in line or "all runs:" in line) and "crashed:" in line:
                    # boot failed: basic kernel testing failed: failed:
                    assert "failed:" not in line
                    result_dict[wait_for_result] = "bad"
                    wait_for_result = None
    assert False


def get_test_results_stageC(cause_bisect_log):
    cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % cause_bisect_log)
    testing_commit_result_dict = dict()
    testing_commit_list = []
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            line = line.strip().lower()
            if "revisions tested" in line:
                return testing_commit_result_dict
            elif "testing commit" in line:
                testing_commit_list.append(line.split()[2])
            elif "# git bisect" in line and "# git bisect start" not in line:
                test_result = line.split()[3]
                assert test_result in ("skip", "good", "bad")
                testing_commit_result_dict[line.split()[4]] = test_result
    assert False


def analyze_failure_cause(bug_id, cause_bisect_log, ground_truth):
    try:
        cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % cause_bisect_log)
        stage = None
        crash_commit = None
        all_version_correct = None
        all_commit_correct = None
        stageA_failure_flag = False
        stageA_run_flag = False
        with open(cause_bisect_path, 'r', encoding='utf-8') as f:
            for line in f.readlines():
                line = line.strip().lower()
                if stage is None:
                    if "bisecting cause commit" in line:
                        stage = 'Stage A'
                        crash_commit = line.split()[-1]
                elif stage == 'Stage A':
                    if "testing release" in line:
                        stage = 'Stage B'
                    elif ("run #" in line or "all runs:" in line) and "boot failed:" not in line and "basic kernel testing failed:" not in line and "failed to run binary in vm" not in line and "failed to run command in vm" not in line:
                        stageA_run_flag = True
                    elif "revisions tested" in line:
                        stageA_failure_flag = True
                    elif stageA_failure_flag:
                        if stageA_run_flag:
                            assert ERROR_NOT_REPRODUCED in line
                            return stage, T2, crash_commit, bug_id
                        else:
                            return stage, T1, crash_commit, bug_id
                elif stage == 'Stage B':
                    if all_version_correct is None:
                        version_test_results = get_test_results_stageB(cause_bisect_log)
                        for v, r in version_test_results.items():
                            if r == 'good' and is_ancestor(ground_truth, v):
                                return stage, T2, v, bug_id
                            elif r == 'bad' and not is_ancestor(ground_truth, v):
                                return stage, T3, v, bug_id
                        all_version_correct = True
                    else:
                        if "# git bisect start" in line:
                            stage = 'Stage C'
                        elif BUG_ON_OLD_RELEASE in line:
                            return stage, C2, None, bug_id
                        elif ERROR_TIMEOUT in line:
                            return stage, C1, None, bug_id
                else:
                    assert stage == 'Stage C'
                    if all_commit_correct is None:
                        commit_test_results = get_test_results_stageC(cause_bisect_log)
                        for c, r in commit_test_results.items():
                            if r == 'good' and is_ancestor(ground_truth, c):
                                return stage, T2, c, bug_id
                            elif r == 'bad' and not is_ancestor(ground_truth, c):
                                return stage, T3, c, bug_id
                        all_commit_correct = True
                    else:
                        if ERROR_TIMEOUT in line:
                            return stage, C1, None, bug_id
        assert False # any other reason?
    except:
        return None, None, None, bug_id


def excel_reader(path):
    df = pandas.read_excel(path, sheet_name='dataset')
    df_dict = df.to_dict()

    data = []
    for i in range(df.shape[0]):
        row = dict()
        for k in df.keys():
            row[k] = df_dict[k][i]
        data.append(row)
    return data


if __name__ == "__main__":
    path = os.path.join(DATA_DIR, "syzbot_bisect_dataset.xlsx")
    data = excel_reader(path)
    process_pool = Pool(processes=os.cpu_count())
    analysis_result = []
    for row in data:
        bug_id = row['bug_id']
        cause_bisect_log = row['cause_bisect_log']
        result_commit = row['result_commit']
        ground_truth = row['ground_truth']
        if result_commit == "no output" or ground_truth not in str2list(result_commit):
            analysis_result.append(process_pool.apply_async(analyze_failure_cause, args=(bug_id, cause_bisect_log, ground_truth), callback=print))

    process_pool.close()
    process_pool.join()

    failure_cause_breakdown_result = dict()
    for r in analysis_result:
        wrong_stage, reason, wrong_commit, bug_id = r.get()
        assert wrong_stage is not None and reason is not None
        detail = "%s %s" % (wrong_stage, reason)
        if detail not in failure_cause_breakdown_result:
            failure_cause_breakdown_result[detail] = []
        failure_cause_breakdown_result[detail].append(bug_id)

    print("================Failure Cause Analysis================")
    for k, v in sorted(failure_cause_breakdown_result.items(), key=lambda x: x[0]):
        print(k, len(v), "%.1f%%" % (len(v) / len(analysis_result) * 100))
