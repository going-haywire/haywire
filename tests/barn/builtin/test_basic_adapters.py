def test_int_to_float_adapter_exists_and_converts():
    from haywire.barn.builtin.adapters.basic_adapters import IntToFloatAdapter

    adapter = IntToFloatAdapter()
    assert adapter.convert(3) == 3.0
