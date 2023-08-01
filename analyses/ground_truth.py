import pymysql as mysql

from config import DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

conn = mysql.connect(host=DB_IP, port=DB_PORT,
                     user=DB_USER, passwd=DB_PWD, db=DB_NAME)
cursor = conn.cursor()

sql = "SELECT bug_id, gt_by_time FROM syzbot_bug_info WHERE gt_by_time is not NULL and fixes_field_filter = 0"
cursor.execute(sql)
data = cursor.fetchall()

update_sql = "UPDATE syzbot_bug_info SET ground_truth = %s WHERE bug_id = %s"
for bug_id, gt_by_time in data:
    ground_truth = gt_by_time.split(",")[-1]
    print (ground_truth, bug_id)
    # cursor.execute(update_sql, (ground_truth, bug_id))
    # conn.commit()

cursor.close()
conn.close()
