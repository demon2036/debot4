from debot4.v6.golden_dogs.x_exact_scan import XSearchSeed, exact_ca_x_tasks


def _seed(index: int, window: int = 1_000) -> XSearchSeed:
    return XSearchSeed(
        address="0x" + f"{index:040x}", name=f"币{index}", symbol=f"T{index}",
        created_at=window + index, peak_at=window + 100 + index,
        window_start=window, window_end_exclusive=window + 604_800,
        peak_fdv_usd="500000", max_kols=index % 2,
    )


def test_every_exact_ca_gets_two_complementary_searches() -> None:
    seeds = tuple(_seed(index) for index in range(1, 7))
    tasks = exact_ca_x_tasks(seeds, batch_size=5)
    assert len(tasks) == 4
    assert {item.lane for item in tasks} == {"authored_posts", "identity_attribution"}
    assert all("$500,000" in item.prompt for item in tasks)
    for seed in seeds:
        matching = [task for task in tasks if seed.address in task.addresses]
        assert len(matching) == 2
        assert all(seed.address in task.prompt for task in matching)


def test_tasks_never_mix_fixed_windows() -> None:
    tasks = exact_ca_x_tasks((_seed(1), _seed(2, 700_000)), batch_size=5)
    assert len(tasks) == 4
    assert all(len(task.addresses) == 1 for task in tasks)


def test_shadow_wallet_is_optional_and_may_be_days_early() -> None:
    prompts = "\n".join(task.prompt for task in exact_ca_x_tasks((_seed(1),)))
    assert "KOL can be real without a wallet" in prompts
    assert "several days before" in prompts
    assert "only a candidate" in prompts
    assert "never a requirement" in prompts


def test_bucketed_peak_may_precede_second_precision_creation_time() -> None:
    seed = _seed(1)
    earlier_peak = XSearchSeed(
        address=seed.address, name=seed.name, symbol=seed.symbol,
        created_at=1_100, peak_at=1_080, window_start=1_000,
        window_end_exclusive=605_800, peak_fdv_usd="500000", max_kols=1,
    )
    assert exact_ca_x_tasks((earlier_peak,))[0].addresses == (seed.address,)
