import { expect, type Page } from "@playwright/test";
import path from "node:path";

// Exercise the real user-upload path independently of catalog publication.
// These photographs are test inputs, not evidence of a garment quality pass.
export async function uploadTestPhotos(page: Page) {
  await page
    .getByLabel("Your person photo", { exact: true })
    .setInputFiles(path.resolve("../data/raw/studio-person.jpg"));
  await page
    .getByLabel("Your garment", { exact: true })
    .setInputFiles(path.resolve("../data/raw/navy-tee.jpg"));
  await expect(
    page.getByAltText("Selected garment conditioning image"),
  ).toBeVisible();
}
