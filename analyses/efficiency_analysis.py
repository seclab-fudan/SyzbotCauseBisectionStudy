import pymysql as mysql
import git
import numpy as np
import json
import os
import re
from multiprocessing import Pool

from config import DATA_DIR, DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

LINUX_REPO = git.Repo(os.path.join(DATA_DIR, 'linux'))
LINUX_NEXT_REPO = git.Repo(os.path.join(DATA_DIR, 'linux-next-history'))


def get_commit_list_between(commit_range, to_cmp=None):
    try:
        repo = LINUX_REPO
        if to_cmp is not None:
            repo.commit(to_cmp)
        return repo.git.rev_list(commit_range).split()
    except:
        repo = LINUX_NEXT_REPO
        if to_cmp is not None:
            repo.commit(to_cmp)
        return repo.git.rev_list(commit_range).split()


def get_bisection_range(cause_bisect_log):
    cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % cause_bisect_log)
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            line = line.strip().lower()
            if "# git bisect start" in line:
                _, bad, good = line.rsplit(maxsplit=2)
                return len(get_commit_list_between("%s..%s" % (good, bad)))
    print("error when processing", cause_bisect_log)
    assert False


def parse_time_str(time_str):
    result = re.match("(\d+h)?(\d+m)?(\d+\.\d+s)", time_str)
    h = 0
    m = 0
    s = 0
    if result is None:
        assert time_str == '0s'
        return (h, m, s)

    hr = result.group(1)
    mr = result.group(2)
    sr = result.group(3)
    if hr is not None:
        h = int(hr[:-1])
    if mr is not None:
        m = int(mr[:-1])
    if sr is not None:
        s = int(sr.split(".")[0])
    return (h, m, s)


def parse_time_tuple_h(t):
    h, m, s = t
    return h + m / 60 + s / 3600


def get_time_info(cause_bisect_log):
    cause_bisect_path = os.path.join(DATA_DIR, "/bisection_log/%s.txt" % cause_bisect_log)
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            line = line.strip().lower()
            if "revisions tested" in line:
                # print(line)
                result = re.search(r"revisions tested: .*, total time: (.*) \(build: (.*), test: .*\)", line)
                return parse_time_tuple_h(parse_time_str(result.group(1))), parse_time_tuple_h(parse_time_str(result.group(2)))
    print("error when processing", cause_bisect_log)
    assert False


if __name__ == "__main__":
    # build time
    conn = mysql.connect(host=DB_IP, port=DB_PORT, user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()
    sql = "SELECT bug_id, cause_bisect_log, testing_commit_num FROM syzbot_bug_info WHERE ground_truth is not NULL"
    cursor.execute(sql)
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    total_time_list = []
    build_time_list = []
    commit_num_list = []
    for bug_id, cause_bisect_log, testing_commit_num in data:
        total_time, build_time = get_time_info(cause_bisect_log)
        total_time_list.append(total_time)
        build_time_list.append(build_time)
        commit_num_list.append(testing_commit_num)
    print("avg test time of a commit: %.2fh, avg build time: %.2fh" % (np.sum(total_time_list) / np.sum(commit_num_list), np.sum(build_time_list) / np.sum(commit_num_list)))
    print("avg test time of a commit: %.2fmin, avg build time: %.2fmin" % (np.sum(total_time_list) / np.sum(commit_num_list) * 60, np.sum(build_time_list) / np.sum(commit_num_list) * 60))

    # exit() # comment this line if you want to run the following code

    # commit tests
    conn = mysql.connect(host=DB_IP, port=DB_PORT, user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()
    sql = "SELECT bug_id, cause_bisect_log, bisect_time, version_test_num, testing_commit_num, unresolved_commit_num_stagec FROM syzbot_bug_info WHERE ground_truth is not NULL"
    cursor.execute(sql)
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    time_list = []
    for bug_id, cause_bisect_log, bisect_time, version_test_num, testing_commit_num, unresolved_commit_num_stagec in data:
        time_list.append(parse_time_tuple_h(parse_time_str(bisect_time)))
    avg_time = np.mean(time_list)
    print("avg bisect time: %.2fh" % avg_time)

    process_pool = Pool(processes=30)
    multi_res = []
    actual_commit_num_list = []
    unresolved_commit_num_list = []
    for bug_id, cause_bisect_log, bisect_time, version_test_num, testing_commit_num, unresolved_commit_num_stagec in data:
        this_time = parse_time_tuple_h(parse_time_str(bisect_time))
        if this_time > avg_time and testing_commit_num > version_test_num:
            multi_res.append(process_pool.apply_async(get_bisection_range, args=(cause_bisect_log,)))
            actual_commit_num_list.append(testing_commit_num - version_test_num)
            unresolved_commit_num_list.append(unresolved_commit_num_stagec)

    process_pool.close()
    process_pool.join()

    expected_commit_num_list = []
    for r in multi_res:
        commit_range = r.get()
        expected_commit_num_list.append(np.log2(commit_range))

    assert len(expected_commit_num_list) == len(actual_commit_num_list) == len(unresolved_commit_num_list)

    print("#commits spending more time than avg (ever enter stage C):", len(expected_commit_num_list))
    print("Avg. expected commit number: %.2f, actual commit number: %.2f, unresolved commit number: %.2f" % (np.mean(expected_commit_num_list), np.mean(actual_commit_num_list), np.mean(unresolved_commit_num_list)))
    print("Mdn. expected commit number: %.2f, actual commit number: %.2f, unresolved commit number: %.2f" % (np.median(expected_commit_num_list), np.median(actual_commit_num_list), np.median(unresolved_commit_num_list)))
