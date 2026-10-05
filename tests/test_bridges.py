"""Bridge logic: pure functions, no network."""
import pytest

from bridges.basescan_earnings import new_earnings, usdc_to_sats

PAY_TO = "0x2091125bFE4259b2CfA889165Beb6290d0Df5DeA"
BTC = 86000.0


def tx(to=PAY_TO, value="5000", symbol="USDC", h="0xabc", ts="1700000000"):
    return {"hash": h, "to": to, "value": value, "tokenSymbol": symbol,
            "timeStamp": ts}


def test_usdc_to_sats():
    # $0.005 at $86k BTC ~= 5.8 sats
    assert usdc_to_sats(0.005, BTC) == 5
    assert usdc_to_sats(1.0, 100000.0) == 1000
    with pytest.raises(ValueError):
        usdc_to_sats(1.0, 0)


def test_new_earnings_happy_path():
    out = new_earnings([tx()], PAY_TO, set(), BTC)
    assert len(out) == 1
    assert out[0]["sats"] == 5 and out[0]["hash"] == "0xabc"


def test_new_earnings_skips_seen_wrong_to_non_usdc_dust():
    seen = {"0xseen"}
    transfers = [
        tx(h="0xseen"),                                   # already seen
        tx(h="0x1", to="0xdeadbeef"),                     # wrong recipient
        tx(h="0x2", symbol="USDT"),                       # wrong token
        tx(h="0x3", value="0"),                           # dust
        tx(h="0x4", value="1000000"),                     # $1.00 -> real
    ]
    out = new_earnings(transfers, PAY_TO, seen, BTC)
    assert [e["hash"] for e in out] == ["0x4"]
    assert out[0]["sats"] == usdc_to_sats(1.0, BTC)


def test_new_earnings_case_insensitive_address():
    out = new_earnings([tx(to=PAY_TO.upper())], PAY_TO.lower(), set(), BTC)
    assert len(out) == 1


def test_new_earnings_bad_rows_skipped():
    out = new_earnings([{"nope": True}, None, tx()], PAY_TO, set(), BTC)
    assert len(out) == 1
