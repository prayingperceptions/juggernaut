"""Bridge logic: pure functions, no network."""
import pytest

from bridges.basescan_earnings import new_earnings, usdc_to_sats
from bridges.base_rpc_earnings import (
    TRANSFER_TOPIC,
    build_log_filter,
    pad_topic_address,
    parse_transfer_log,
)

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


# -- base_rpc_earnings (keyless RPC bridge) --------------------------------

def test_pad_topic_address():
    padded = pad_topic_address(PAY_TO)
    assert padded == "0x" + "0" * 24 + PAY_TO[2:].lower()
    assert len(padded) == 66
    assert pad_topic_address(PAY_TO.lower()) == padded
    with pytest.raises(ValueError):
        pad_topic_address("0xdead")  # too short
    with pytest.raises(ValueError):
        pad_topic_address("not-an-address")


def test_build_log_filter():
    f = build_log_filter(PAY_TO, 1000, 2000)
    assert f["fromBlock"] == hex(1000)
    assert f["toBlock"] == hex(2000)
    assert f["address"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert f["topics"][0] == TRANSFER_TOPIC
    assert f["topics"][1] is None  # wildcard: any sender
    assert f["topics"][2] == pad_topic_address(PAY_TO)


def test_parse_transfer_log():
    log = {"transactionHash": "0xabc", "data": hex(5000)}  # 5000 base units
    parsed = parse_transfer_log(log)
    assert parsed == {"hash": "0xabc", "value": 5000}
    assert usdc_to_sats(parsed["value"] / 1e6, BTC) == 5


def test_parse_transfer_log_bad_rows():
    assert parse_transfer_log({}) is None
    assert parse_transfer_log({"transactionHash": "0x1"}) is None
    assert parse_transfer_log({"transactionHash": "0x1", "data": "zzz"}) is None
    assert parse_transfer_log(None) is None


def test_transfer_topic_is_erc20_transfer():
    # keccak256("Transfer(address,address,uint256)")
    assert TRANSFER_TOPIC == \
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
