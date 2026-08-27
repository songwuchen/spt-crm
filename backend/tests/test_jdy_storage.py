"""简道云历史 OSS 虚拟附件 id 编解码。"""
from app.domains.attachment.jdy_storage import (
    filename_from_oss_key,
    jdy_attachment_id_from_key,
    parse_jdy_attachment_id,
    is_jdy_oss_attachment_id,
)


def test_jdy_oss_id_roundtrip():
    key = "datahub/app/entry/qiniuKey_合同.pdf"
    vid = jdy_attachment_id_from_key(key)
    assert vid.startswith("jdy-oss:")
    assert parse_jdy_attachment_id(vid) == key
    assert is_jdy_oss_attachment_id(vid)
    assert not is_jdy_oss_attachment_id("jdy-meta:foo.pdf")


def test_filename_from_oss_key():
    assert filename_from_oss_key("datahub/a/b/qiniu_合同.pdf") == "合同.pdf"
    assert filename_from_oss_key("plain/name.pdf") == "name.pdf"
