from src.fst_registry import InventoryRegistry, InventoryItem

def test_init_inventory_registry():
    reg = InventoryRegistry('config/')

    assert hasattr(reg, 'data')
    data = reg.data
    assert isinstance(data, dict)
    for key, value in data.items():
        assert type(key) is str
        assert isinstance(value, InventoryItem)
    
    assert '<N>' in data
    assert data['<N>'].type == 'class'
    expected_nasal_phones = ['m', 'n', 'ɲ', 'ŋ']

    for item in data['<N>'].children:
        assert item.type == 'phone'
        assert item.value in expected_nasal_phones

    assert '<V>' in data
    assert data['<V>'].type == 'class'
    expected_vowel_subclasses = ["<V_High>", "<V_Mid>", "<V_Low>"]

    for item in data['<V>'].children:
        assert item.type == 'class'
        assert item.value in expected_vowel_subclasses