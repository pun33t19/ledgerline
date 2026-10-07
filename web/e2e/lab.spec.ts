import { expect, test } from "@playwright/test";
import { TOKEN } from "../playwright.config";

const column = (page: import("@playwright/test").Page, name: string) => page.getByRole("region", { name });

test.describe("Attack Simulation Lab", () => {
  test("refuses browsers that did not come through the printed link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Open the Lab from its link" })).toBeVisible();
  });

  test("lists the attacks and removes the token from the address bar", async ({ page }) => {
    await page.goto(`/?token=${TOKEN}`);
    await expect(page.getByRole("heading", { name: /Watch an AI agent get compromised/ })).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(7); // header + 6 attacks
    expect(page.url()).not.toContain("token=");
  });

  test("silent rug pull: stolen without Ledgerline, stopped with it, and stolen again with the check off", async ({
    page,
  }) => {
    await page.goto(`/?token=${TOKEN}`);
    await page
      .getByRole("row", { name: /Silent rug pull/ })
      .getByRole("button", { name: "Run" })
      .click();
    await expect(
      page.getByRole("heading", { name: "Silent rug pull (host never re-reads the menu)" }),
    ).toBeVisible();

    await expect(column(page, "Without Ledgerline").getByText("The attacker got the secret")).toBeVisible();
    await expect(column(page, "With Ledgerline").getByText("Stopped before any harm")).toBeVisible();
    await expect(
      column(page, "With Ledgerline").getByText("Stopped by Check before every call."),
    ).toBeVisible();

    // Inspect Ledgerline's decision.
    await column(page, "With Ledgerline")
      .getByText(/^blocked:/)
      .click();
    const sheet = page.getByRole("dialog");
    await expect(sheet.getByText(/asks the server for that tool's current definition/)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();

    // Switch the control off and run again: now the attack succeeds on both sides.
    await page.getByRole("switch", { name: /Check before every call/ }).click();
    await page.getByRole("button", { name: "Run with these controls" }).click();
    await expect(column(page, "With Ledgerline").getByText("The attacker got the secret")).toBeVisible();
  });

  test("attack replay: steps through how the secret was stolen and where Ledgerline stopped it", async ({
    page,
  }) => {
    await page.goto(`/?token=${TOKEN}`);
    await page.getByRole("button", { name: "Watch a silent rug pull" }).click();
    const replay = page.getByRole("region", { name: "Attack replay" });
    const steps = replay.getByRole("list", { name: "Steps of the attack" }).getByRole("button");

    await expect(steps.last()).toHaveAccessibleName(/Compromised/, { timeout: 30_000 });
    await steps.last().click();
    await expect(
      replay.getByText("Compromised. Nothing stood between your agent and the tool server."),
    ).toBeVisible();
    await replay.getByRole("button", { name: /reads your secrets file/ }).click();
    await expect(
      replay.getByText("The tool server's own code reads your secrets file.", { exact: false }),
    ).toBeVisible();

    await replay.getByRole("tab", { name: /With Ledgerline/ }).click();
    await replay.getByRole("button", { name: /Ledgerline stops the call/ }).click();
    await expect(replay.getByText(/re-read the tool's definition from the server/)).toBeVisible();
    await expect(steps.last()).toHaveAccessibleName(/Your secret never left/);
  });

  test("ledger: the chain verifies, and rewriting the blocked call breaks it at that entry", async ({
    page,
  }) => {
    await page.goto(`/?token=${TOKEN}`);
    await page.getByRole("button", { name: "Watch a silent rug pull" }).click();
    await expect(column(page, "With Ledgerline").getByText("Stopped before any harm")).toBeVisible();
    await page.getByRole("tab", { name: "Ledger", exact: true }).click();
    const ledger = page.getByRole("region", { name: "The ledger" });

    await ledger.getByRole("button", { name: "Verify the chain" }).click();
    await expect(ledger.getByText("Chain intact: all 7 entries verified.")).toBeVisible();

    await ledger.getByRole("button", { name: "Tamper with the ledger" }).click();
    const blocked = ledger.getByRole("article", { name: "Entry 7" });
    await expect(blocked.getByText("blocked by Check before every call")).toBeVisible();
    await blocked.getByRole("button", { name: "Rewrite as allowed" }).click();
    await ledger.getByRole("button", { name: "Verify the chain" }).click();
    await expect(
      ledger.getByText("Entry 7 was changed after it was written", { exact: false }),
    ).toBeVisible();
    await expect(ledger.getByText("Entries 1 to 6 are intact.", { exact: false })).toBeVisible();
    await expect(blocked.getByText("broken here")).toBeVisible();

    await ledger.getByRole("button", { name: "Undo my edits" }).click();
    await ledger.getByRole("button", { name: "Verify the chain" }).click();
    await expect(ledger.getByText("Chain intact: all 7 entries verified.")).toBeVisible();
  });

  test("rug pull: the model's view shows the changed description and that Ledgerline hides it", async ({
    page,
  }) => {
    await page.goto(`/?token=${TOKEN}`);
    await page
      .getByRole("row", { name: /Rug pull \(host re-reads/ })
      .getByRole("button", { name: "Run" })
      .click();
    await expect(column(page, "With Ledgerline").getByText("Stopped before any harm")).toBeVisible();
    await page.getByRole("tab", { name: "What the model reads" }).click();
    await expect(page.getByText("Changed since you approved it.")).toBeVisible();
    await expect(page.getByText("Ledgerline hides it from the model.")).toBeVisible();
  });

  test("tool poisoning states the honest limit", async ({ page }) => {
    await page.goto(`/?token=${TOKEN}`);
    await page
      .getByRole("row", { name: /Tool poisoning/ })
      .getByRole("button", { name: "Run" })
      .click();
    await expect(page.getByText(/Not stopped today/)).toBeVisible();
    await expect(column(page, "With Ledgerline").getByText("The attacker got the secret")).toBeVisible();
  });
});

test("coverage: measures which control stops each attack", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto(`/?token=${TOKEN}`);
  await page.getByRole("link", { name: "Coverage" }).click();
  await expect(page.getByRole("heading", { name: "Which control stops which attack" })).toBeVisible();
  const silent = page.getByRole("row", { name: /Silent rug pull/ });
  await expect(silent).toBeVisible({ timeout: 120_000 });
  await expect(silent.getByRole("cell").nth(3)).toHaveText("Stops it"); // Check before every call
  const parser = page.getByRole("row", { name: /Parser differential/ });
  await expect(parser.getByRole("cell").last()).toHaveText("Stops it"); // Strict message parsing
  await expect(
    page
      .getByRole("row", { name: /Tool poisoning/ })
      .getByRole("cell")
      .last(),
  ).toHaveText("Not stopped yet");
});
