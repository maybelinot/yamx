from yamjinx import YAMJinX
from yamjinx.yamjinx import ToggledData


def test_dump_to_file(tmp_path):
    yamx = YAMJinX()
    file_path = f"{tmp_path}/data.yaml"
    with open(file_path, "w+") as fp:
        yamx.dump(ToggledData(None), fp)

    with open(file_path) as fp:
        data = fp.read()

    assert data == "null\n...\n"


def test_dump_to_(tmp_path):
    yamx = YAMJinX()

    data = yamx.dump_to_string(ToggledData(None))
    assert data == "null\n..."
