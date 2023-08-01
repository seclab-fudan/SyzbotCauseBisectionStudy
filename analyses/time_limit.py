import json
import pymysql as mysql
import numpy as np

from config import DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

def get_timeout_info_stageB(bug_id):
    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT crash_commit_version, version_test_num FROM syzbot_bug_info WHERE bug_id = %s"
    cursor.execute(sql, bug_id)
    crash_commit_version, version_test_num = cursor.fetchone()

    cursor.close()
    conn.close()
    return crash_commit_version, version_test_num - 1


def get_timeout_info_stageC(bug_id):
    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT version_test_num, testing_commit_num FROM syzbot_bug_info WHERE bug_id = %s"
    cursor.execute(sql, bug_id)
    version_test_num, testing_commit_num = cursor.fetchone()

    cursor.close()
    conn.close()
    return testing_commit_num - version_test_num
    

if __name__ == '__main__':
    # Timeout in Stage B
    print("Timeout in Stage B")
    version_num = []
    with open("error_breakdown_detail_new.json", mode='r', encoding='utf-8') as f:
        error_breakdown_detail = json.load(f)
        for k, v in error_breakdown_detail.items():
            if k == 'Stage B L1':
                for bug_id in v:
                    crash_commit_version, stageB_version = get_timeout_info_stageB(bug_id)
                    print(crash_commit_version, stageB_version)
                    version_num.append(stageB_version)
    print("#: %s, Avg number of version tested: %s" % (len(version_num), np.mean(version_num)))

    # Timeout in Stage C
    print("Timeout in Stage C")
    commit_num = []
    with open("error_breakdown_detail_new.json", mode='r', encoding='utf-8') as f:
        error_breakdown_detail = json.load(f)
        for k, v in error_breakdown_detail.items():
            if k == 'Stage C L1':
                for bug_id in v:
                    commit_num.append(get_timeout_info_stageC(bug_id))
    print("#: %s, Avg number of commit tested: %s" % (len(commit_num), np.mean(commit_num)))
