import pandas
import pymysql as mysql
import re
import numpy as np
from collections import Counter
from scipy import stats

from config import DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME
from efficiency_analysis import get_time_info


def format_int(num):
    return "{:,}".format(num)


def format_float(num):
    return "{:,.2f}".format(num)


def list2str(list):
    str = ""
    for ele in list:
        str += ele + ","
    return str.strip(",")


def str2list(str):
    list = []
    if str != '' and str is not None:
        list = str.split(",")
    return list


def table_different_cause_bisection_fix_time():
    no_bisect_commit_output_fix_time_list = []
    correct_bug_fix_time_list = []
    wrong_bug_fix_time_list = []
    total_bug_fix_time_list = []

    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT bug_id, bad_commit, inconclusive_commit, ground_truth, DATEDIFF(patch_time, report_time) as fix_time FROM syzbot_bug_info WHERE ground_truth is NOT NULL and DATEDIFF(patch_time, report_time) >= 0"
    cursor.execute(sql)
    data = cursor.fetchall()

    for bug_id, bad_commit, inconclusive_commit, ground_truth, bug_fix_time in data:
        if bad_commit is None and inconclusive_commit is None:
            no_bisect_commit_output_fix_time_list.append(bug_fix_time)
            total_bug_fix_time_list.append(bug_fix_time)
        else:
            assert bad_commit is not None
            cause_bisection_result_list = [bad_commit]
            if inconclusive_commit is not None:
                cause_bisection_result_list.extend(inconclusive_commit.split(","))

            if ground_truth in cause_bisection_result_list:
                correct_bug_fix_time_list.append(bug_fix_time)
                total_bug_fix_time_list.append(bug_fix_time)
            else:
                wrong_bug_fix_time_list.append(bug_fix_time)
                total_bug_fix_time_list.append(bug_fix_time)

    cursor.close()
    conn.close()

    quartile_nums = np.percentile(
        no_bisect_commit_output_fix_time_list, (25, 50, 75), interpolation="midpoint")
    print("%s & %s (%.2f\%%) & %s & %s & %s & %s \\\\" % (
        "No output", len(no_bisect_commit_output_fix_time_list),
        len(no_bisect_commit_output_fix_time_list) / len(total_bug_fix_time_list) * 100,
        quartile_nums[0], quartile_nums[1], quartile_nums[2],
        format_float(np.mean(no_bisect_commit_output_fix_time_list))))

    quartile_nums = np.percentile(
        correct_bug_fix_time_list, (25, 50, 75), interpolation="midpoint")
    print("%s & %s (%.2f\%%) & %s & %s & %s & %s \\\\" % (
        "Correct", len(correct_bug_fix_time_list),
        len(correct_bug_fix_time_list) / len(total_bug_fix_time_list) * 100,
        quartile_nums[0], quartile_nums[1], quartile_nums[2],
        format_float(np.mean(correct_bug_fix_time_list))))

    quartile_nums = np.percentile(
        wrong_bug_fix_time_list, (25, 50, 75), interpolation="midpoint")
    print("%s & %s (%.2f\%%) & %s & %s & %s & %s \\\\" % (
        "Incorrect", len(wrong_bug_fix_time_list),
        len(wrong_bug_fix_time_list) / len(total_bug_fix_time_list) * 100,
        quartile_nums[0], quartile_nums[1], quartile_nums[2],
        format_float(np.mean(wrong_bug_fix_time_list))))

    print("\\midrule")

    quartile_nums = np.percentile(
        total_bug_fix_time_list, (25, 50, 75), interpolation="midpoint")
    print("%s & %s & %s & %s & %s & %s \\\\" % (
        "\\textbf{Total}", len(total_bug_fix_time_list),
        quartile_nums[0], quartile_nums[1], quartile_nums[2],
        format_float(np.mean(total_bug_fix_time_list))))

    _, p_value = stats.ranksums(correct_bug_fix_time_list, wrong_bug_fix_time_list)
    print("correct vs. incorrect p-value: %s" % p_value)
    _, p_value = stats.ranksums(wrong_bug_fix_time_list, no_bisect_commit_output_fix_time_list)
    print("incorrect vs. no-output p-value: %s" % p_value)

def parse_time_str(time_str):
    result = re.match("(\d+h)?(\d+m)?(\d+\.\d+s)", time_str)
    h = 0
    m = 0
    s = 0
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


def sum_time_duration(duration_list):
    """
    :param duration_list: [(h, m, s), ...]
    :return: total "#h#m#s"
    """
    h = 0
    m = 0
    s = 0
    for (hh, mm, ss) in duration_list:
        h += hh
        m += mm
        s += ss

    if s >= 60:
        m += int(s / 60)
        s = s % 60

    if m >= 60:
        h += int(m / 60)
        m = m % 60

    if h == m == s == 0:
        return "0"

    total_time_str = ""
    if h > 0:
        total_time_str += str(h) + "h"
    if m > 0:
        total_time_str += str(m) + "m"
    if s > 0:
        total_time_str += str(s) + "s"
    return total_time_str


def avg_time_duration(duration_list):
    """
    :param duration_list: [(h, m, s), ...]
    :return: avg of time duration "#h#m#s"
    """
    total_seconds = 0
    for (h, m, s) in duration_list:
        total_seconds += s
        total_seconds += 60 * m
        total_seconds += 3600 * h

    avg_seconds = int(total_seconds / len(duration_list))
    avg_h = int(avg_seconds / 3600)
    avg_m = int((avg_seconds % 3600) / 60)
    avg_s = avg_seconds - avg_h * 3600 - avg_m * 60
    assert avg_s == (avg_seconds % 3600) % 60

    if avg_h == avg_m == avg_s == 0:
        return "0"

    avg_time_str = ""
    if avg_h > 0:
        avg_time_str += str(avg_h) + "h"
    if avg_m > 0:
        avg_time_str += str(avg_m) + "m"
    if avg_s > 0:
        avg_time_str += str(avg_s) + "s"
    return avg_time_str


def median_time_duration(duration_list):
    """
    :param duration_list: [(h, m, s), ...]
    :return: mdn of time duration "#h#m#s"
    """
    sorted_duration_list = sorted(
        duration_list, key=lambda x: (x[0], x[1], x[2]), reverse=False)
    if len(sorted_duration_list) % 2 == 1:
        median_h, median_m, median_s = sorted_duration_list[int(
            len(sorted_duration_list) / 2)]
        median_time_str = ""
        if median_h > 0:
            median_time_str += str(median_h) + "h"
        if median_m > 0:
            median_time_str += str(median_m) + "m"
        if median_s > 0:
            median_time_str += str(median_s) + "s"
        return median_time_str
    else:
        assert len(sorted_duration_list) > 0
        return avg_time_duration([sorted_duration_list[int(len(sorted_duration_list) / 2)], sorted_duration_list[int(len(sorted_duration_list) / 2) - 1]])


def table_overall_performance():
    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT cause_bisect_log, crash_commit_version, version_test_num, testing_commit_num, bisect_time, bad_commit, inconclusive_commit, ground_truth FROM syzbot_bug_info WHERE ground_truth is not NULL"
    cursor.execute(sql)
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    info_dict = {"Total": {"version_commit_num_list": [], "testing_commit_num_list": [], "bisect_time_list": [], "bug_wo_iso": 0, "correct": 0, "incorrect": 0, "build_time_list": [], "test_time_list": []}}
    for cause_bisect_log, crash_commit_version, version_test_num, testing_commit_num, bisect_time, bad_commit, inconclusive_commit, ground_truth in data:
        if crash_commit_version.startswith('v6.'):
            crash_commit_version = 'v6.0'
        elif crash_commit_version.startswith('v5.'):
            crash_commit_version = 'v5.0'
        elif crash_commit_version.startswith('v4.'):
            crash_commit_version = 'v4.0'

        if crash_commit_version not in info_dict:
            info_dict[crash_commit_version] = {"version_commit_num_list": [], "testing_commit_num_list": [], "bisect_time_list": [], "bug_wo_iso": 0, "correct": 0, "incorrect": 0, "build_time_list": [], "test_time_list": []}

        bad_num = len(str2list(bad_commit))
        inconclusive_num = len(str2list(inconclusive_commit))
        if bad_num + inconclusive_num == 0:
            info_dict[crash_commit_version]["bug_wo_iso"] += 1
            info_dict["Total"]["bug_wo_iso"] += 1
        else:
            iso_commit_list = [bad_commit]
            iso_commit_list.extend(str2list(inconclusive_commit))
            assert len(iso_commit_list) == bad_num + inconclusive_num
                
            if ground_truth in iso_commit_list:
                info_dict[crash_commit_version]["correct"] += 1
                info_dict["Total"]["correct"] += 1
            else:
                info_dict[crash_commit_version]["incorrect"] += 1
                info_dict["Total"]["incorrect"] += 1

        # version tested in Stage B
        info_dict[crash_commit_version]["version_commit_num_list"].append(version_test_num - 1)
        info_dict["Total"]["version_commit_num_list"].append(version_test_num - 1)

        # commit tested in Stage C
        info_dict[crash_commit_version]["testing_commit_num_list"].append(testing_commit_num - version_test_num)
        info_dict["Total"]["testing_commit_num_list"].append(testing_commit_num - version_test_num)
        
        bisect_time_h = parse_time_tuple_h(parse_time_str(bisect_time))
        info_dict[crash_commit_version]["bisect_time_list"].append(bisect_time_h)
        info_dict["Total"]["bisect_time_list"].append(bisect_time_h)

        # ablation of build and test time
        total_time, build_time = get_time_info(cause_bisect_log)
        info_dict["Total"]["build_time_list"].append(build_time)
        info_dict["Total"]["test_time_list"].append(total_time - build_time)
        info_dict[crash_commit_version]["build_time_list"].append(build_time)
        info_dict[crash_commit_version]["test_time_list"].append(total_time-build_time)

    related_version_list = []
    for k, _ in info_dict.items():
        if k != "Total":
            related_version_list.append(k)
    sorted_version_list = sorted(related_version_list,
                                 key=lambda x: (int(x[1:].split(".")[0]),
                                                int(x[1:].split(".")[1])),
                                 reverse=True)

    for version in sorted_version_list:
        bug_num = info_dict[version]["bug_wo_iso"] + info_dict[version]["correct"] + info_dict[version]["incorrect"]
        print("%s & %s & %s (%.0f\%%) & %s (%.0f\%%) & %s (%.0f\%%) & & %s & %s & %sh & %sh & %sh\\\\" % (
            version, format_int(bug_num),
            format_int(info_dict[version]["bug_wo_iso"]),
            info_dict[version]["bug_wo_iso"] / bug_num * 100,
            format_int(info_dict[version]["correct"]),
            info_dict[version]["correct"] / bug_num * 100,
            format_int(info_dict[version]["incorrect"]),
            info_dict[version]["incorrect"] / bug_num * 100,
            format_float(
                np.mean(info_dict[version]["version_commit_num_list"])),
            format_float(
                np.mean(info_dict[version]["testing_commit_num_list"])),
            format_float(
                np.mean(info_dict[version]["build_time_list"])),
            format_float(
                np.mean(info_dict[version]["test_time_list"])),
            format_float(
                np.mean(info_dict[version]["bisect_time_list"])),
        ))

    print("\\midrule")

    version = "Total"
    bug_num = info_dict[version]["bug_wo_iso"] + info_dict[version]["correct"] + info_dict[version]["incorrect"]
    print("%s & %s & %s (%.0f\%%) & %s (%.0f\%%) & %s (%.0f\%%) & & %s & %s & %sh & %sh & %sh\\\\" % (
        "\\textbf{Total}", format_int(bug_num),
        format_int(info_dict[version]["bug_wo_iso"]),
        info_dict[version]["bug_wo_iso"] / bug_num * 100,
        format_int(info_dict[version]["correct"]),
        info_dict[version]["correct"] / bug_num * 100,
        format_int(info_dict[version]["incorrect"]),
        info_dict[version]["incorrect"] / bug_num * 100,
        format_float(
            np.mean(info_dict[version]["version_commit_num_list"])),
        format_float(
            np.mean(info_dict[version]["testing_commit_num_list"])),
        format_float(
            np.mean(info_dict[version]["build_time_list"])),
        format_float(
            np.mean(info_dict[version]["test_time_list"])),
        format_float(
            np.mean(info_dict[version]["bisect_time_list"])),
    ))

    less_than_avg = 0
    less_than_8h = 0
    avg_time = np.mean(info_dict[version]["bisect_time_list"])
    for t in info_dict[version]["bisect_time_list"]:
        if t <= avg_time:
            less_than_avg += 1
        
        if t <= 8:
            less_than_8h += 1
    print("bisect time less than avg: %s %.2f%%" % (less_than_avg, less_than_avg / len(info_dict[version]["bisect_time_list"]) * 100))
    print("bisect time less than 8h: %s %.2f%%" % (less_than_8h, less_than_8h / len(info_dict[version]["bisect_time_list"]) * 100))
    print("avg. time/commit: %.2fmin" % (np.sum(info_dict[version]["bisect_time_list"]) / (len(info_dict[version]["version_commit_num_list"]) + np.sum(info_dict[version]["version_commit_num_list"]) + np.sum(info_dict[version]["testing_commit_num_list"])) * 60))


def bisected_commit_num_distribution():
    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT bug_id, bad_commit, inconclusive_commit FROM syzbot_bug_info WHERE ground_truth is NOT NULL"
    cursor.execute(sql)
    data = cursor.fetchall()

    num_list = []
    for _, bad_commit, inconclusive_commit in data:
        if bad_commit is None and inconclusive_commit is None:
            num_list.append(0)
        else:
            assert bad_commit is not None
            cause_bisection_result_list = [bad_commit]
            if inconclusive_commit is not None:
                cause_bisection_result_list.extend(inconclusive_commit.split(","))

            num = len(cause_bisection_result_list)
            assert num == len(set(cause_bisection_result_list))
            num_list.append(num)

    cursor.close()
    conn.close()

    res = Counter(num_list)
    res = dict(res)
    more_than1_count = 0
    for k, v in sorted(res.items(), key=lambda x: x[0]):
        print(k, v)
        if k > 1:
            more_than1_count += v

    print("%s: %s (%.2f%%)" % (0, res[0], res[0]/len(num_list)*100))
    print("%s: %s (%.2f%%)" % (1, res[1], res[1]/len(num_list)*100))
    print("%s: %s (%.2f%%)" % (">1", more_than1_count, more_than1_count/len(num_list)*100))


if __name__ == "__main__":
    # TABLE I: overall performance of cause bisection
    table_overall_performance()

    # TABLE VI: impact on bug-fixing time (day)
    table_different_cause_bisection_fix_time()

    # distribution of #result commits
    bisected_commit_num_distribution()
