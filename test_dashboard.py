import sys
import os
import pandas as pd
from unittest.mock import patch, MagicMock
import pytest

# Pridanie cesty k adresáru, aby sme mohli importovať dashboard
# Toto je potrebné, pretože testovací súbor je v rovnakom adresári ako modul, ktorý testujeme.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Teraz môžeme importovať modul dashboard.
# Musíme ho premenovať, pretože 'dashboard' nie je platný názov modulu, ak by obsahoval špeciálne znaky.
# V tomto prípade je názov súboru v poriadku.
import dashboard


@pytest.fixture(autouse=True)
def clear_cache():
    """
    Fixture, ktorá pred každým testom vymaže Streamlit cache funkcie load_data,
    aby výsledky jedného testu neovplyvňovali ďalší.
    """
    dashboard.load_data.clear()
    yield


@pytest.fixture
def mock_streamlit():
    """
    Fixture na mockovanie (simulovanie) funkcií Streamlitu, aby testy mohli bežať
    bez skutočného spúšťania Streamlit servera.
    """
    mock_st = MagicMock()
    # Nahradíme objekt 'st' priamo v module dashboard, aby volania st.error() a
    # pod. v tele testovanej funkcie smerovali na náš mock.
    with patch.object(dashboard, 'st', mock_st):
        yield mock_st


def test_load_data_file_not_found(mock_streamlit):
    """
    Test 1: Overí správanie, keď dátový súbor neexistuje.
    Očakávame, že funkcia vráti None a zavolá st.error.
    """
    with patch('os.path.exists', return_value=False):
        result = dashboard.load_data()
        assert result is None
        # Overíme, či bola zavolaná funkcia st.error s očakávanou správou
        mock_streamlit.error.assert_called_once_with(
            f"Súbor '{dashboard.SUBOR_HISTORIA}' nebol nájdený. Spustite najprv hlavnú aplikáciu, aby sa vygeneroval."
        )


def test_load_data_success():
    """
    Test 2: Overí úspešné načítanie a spracovanie korektných dát.
    Vytvoríme dočasný CSV súbor v pamäti.
    """
    # Vzorové dáta, ktoré simulujú obsah CSV súboru
    csv_data = (
        "Dátum;Čas;PIN;Meno;Typ;Chyba;Hodnota\n"
        "2025-12-01;10:00:00;1111;Lukáš BENDÍK;PRIDANÉ;BX726 Lateral - NEDOPENENÁ;1\n"
        "2025-12-01;10:05:00;2222;Miroslav GALLIK;PRIDANÉ;M7 - ROZTRHNUTÁ;1\n"
        "2025-12-01;10:10:00;1111;Lukáš BENDÍK;ODSTRÁNENÉ;BX726 Lateral - NEDOPENENÁ;0\n"
        "2025-12-01;10:15:00;9999;Technológ;RESTART;SYS;0\n"
    )

    # DataFrame vytvoríme PRED aktiváciou mocku, aby pd.read_csv v tomto volání
    # použil skutočný pandas a nie mock.
    from io import StringIO
    df = pd.read_csv(StringIO(csv_data), delimiter=';')

    # Mockujeme funkcie pre prácu so súborovým systémom
    with patch('os.path.exists', return_value=True):
        with patch('pandas.read_csv', return_value=df):
            # Spustíme testovanú funkciu
            result_df = dashboard.load_data()

            # Overenia
            assert result_df is not None
            assert isinstance(result_df, pd.DataFrame)
            assert len(result_df) == 4

            # 1. Overenie správnej konverzie dátumu
            assert pd.api.types.is_datetime64_any_dtype(result_df['Dátum'])

            # 2. Overenie správneho rozdelenia stĺpca 'Chyba'
            assert 'Hlavná Chyba' in result_df.columns
            assert 'Pod-chyba' in result_df.columns
            
            # Očakávané hodnoty v nových stĺpcoch
            expected_hlavna = ['BX726 Lateral', 'M7', 'BX726 Lateral', 'SYS']
            expected_pod = ['NEDOPENENÁ', 'ROZTRHNUTÁ', 'NEDOPENENÁ', '']
            
            assert result_df['Hlavná Chyba'].tolist() == expected_hlavna
            assert result_df['Pod-chyba'].tolist() == expected_pod


def test_load_data_parsing_error(mock_streamlit):
    """
    Test 3: Overí správanie pri chybe počas spracovania CSV (napr. zlý formát).
    Očakávame, že funkcia vráti None a zavolá st.error.
    """
    # Mockujeme os.path.exists, aby sme sa dostali k časti s čítaním súboru
    with patch('os.path.exists', return_value=True):
        # Simulujeme chybu pri volaní pd.read_csv
        error_message = "Test parsing error"
        with patch('pandas.read_csv', side_effect=Exception(error_message)):
            result = dashboard.load_data()

            # Overíme, že výsledok je None a bola zaznamenaná chyba
            assert result is None
            mock_streamlit.error.assert_called_once_with(f"Chyba pri načítavaní CSV súboru: {error_message}")