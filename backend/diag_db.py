# -*- coding: utf-8 -*-
"""一次性数据库诊断脚本：核对行业知识模块的 mock 数据是否满足代码查询条件。"""
import sys
import psycopg2
import psycopg2.extras

DSN = dict(host="localhost", port=5433, dbname="buildingai",
           user="xiaozhuo", password="20040628003x")


def section(t):
    print("\n" + "=" * 60)
    print("# " + t)
    print("=" * 60)


def q(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()


def main():
    conn = psycopg2.connect(**DSN)
    conn.set_client_encoding("UTF8")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    section("连接成功，数据库版本")
    print(q(cur, "SELECT version()")[0]["version"])

    section("相关表分布在哪些 schema（datasets / segments / 行业知识表）")
    rows = q(cur, """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_name IN (
            'datasets','datasets_segments','datasets_documents',
            'industry_knowledge_skills','industry_knowledge_query_logs',
            'industry_knowledge_query_references','industry_knowledge_feedback'
        )
        ORDER BY table_name, table_schema
    """)
    for r in rows:
        print(f"  {r['table_schema']}.{r['table_name']}")
    if not rows:
        print("  ！没找到任何相关表")

    section("chinese_zh 全文检索配置是否存在")
    rows = q(cur, "SELECT cfgname FROM pg_ts_config WHERE cfgname = 'chinese_zh'")
    print("  存在 chinese_zh" if rows else "  ！不存在 chinese_zh（代码默认用它，会报错）")
    print("  可用的 ts_config:", [r["cfgname"] for r in q(cur, "SELECT cfgname FROM pg_ts_config ORDER BY cfgname")])

    section("行业知识 skill（前 10 条）")
    try:
        rows = q(cur, """
            SELECT id, skill_name, dataset_id, retrieval_mode, top_k,
                   max_context_chars, enabled
            FROM wuyu_industry.industry_knowledge_skills
            ORDER BY created_at LIMIT 10
        """)
        if not rows:
            print("  ！skills 表为空")
        for r in rows:
            print(f"  id={r['id']} enabled={r['enabled']} mode={r['retrieval_mode']} "
                  f"top_k={r['top_k']} dataset_id={r['dataset_id']} name={r['skill_name']}")
    except Exception as e:
        print("  查询失败:", e)
        conn.rollback()

    # 探测 datasets_segments 实际所在 schema
    seg_schema = None
    for r in q(cur, """
        SELECT table_schema FROM information_schema.tables
        WHERE table_name='datasets_segments'"""):
        seg_schema = r["table_schema"]

    if seg_schema:
        section(f"datasets_segments 字段与样本（schema={seg_schema}）")
        cols = q(cur, """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema=%s AND table_name='datasets_segments'
            ORDER BY ordinal_position""", (seg_schema,))
        print("  字段:", [(c["column_name"], c["data_type"]) for c in cols])
        try:
            rows = q(cur, f"""
                SELECT enabled, status, count(*) AS n
                FROM {seg_schema}.datasets_segments
                GROUP BY enabled, status ORDER BY n DESC LIMIT 20""")
            print("  enabled/status 分布（代码要求 enabled=1 且 status='completed'）:")
            for r in rows:
                print(f"    enabled={r['enabled']!r} status={r['status']!r} 行数={r['n']}")
        except Exception as e:
            print("  统计失败:", e); conn.rollback()

    cur.close(); conn.close()
    print("\n诊断完成。")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
