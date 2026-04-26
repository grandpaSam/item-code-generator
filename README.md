# item_code_generation

A custom Frappe/ERPNext app for robust variant SKU generation using `{placeholder}` tokens in template Item Codes.

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/grandpasam)

---

## How SKU Generation Works

Define a template Item whose `item_code` contains `{attribute_name}` placeholders:

```
Template item_code:   SHIRT{Size}{Color}
```

Each placeholder maps to an **Item Attribute** by name (case-insensitive).
The substitution value comes from the **SKU Code** field on each **Item Attribute Value**.

### Example

| Attribute | Value  | SKU Code |
|-----------|--------|----------|
| Size      | Small  | `SM`     |
| Size      | Large  | `LG`     |
| Color     | Red    | `RED`    |
| Color     | Blue   | `BLU`    |

Creating a variant with `Size=Small` + `Color=Red` produces:
```
SHIRTSMRED
```

---

## Features

### SKU Code custom field
A dedicated **SKU Code** column is added to the Attribute Values table inside **Stock → Item Attribute**. Fill in the short code for each value and it will be used automatically during variant generation.

### Live SKU preview on variant drafts
When a new variant draft is opened, the correct generated item code is shown in the `item_code` field immediately

### Autocomplete for template item codes
On template items, typing `{` in the Item Code field opens an autocomplete dropdown populated from your existing Item Attributes.

### Bidirectional validation on save
When saving a template item, the app checks both directions:
- **Placeholders with no matching attribute** — Makes sure you dont forget to go to the variants tab
- **Attributes with no matching placeholder** — catches attributes added to the Attributes tab but forgotten in the item code pattern

---

## Installation

```bash
# From your bench directory
bench get-app item_code_generation https://github.com/grandpaSam/item-code-generator

bench --site your.site.com install-app item_code_generation
bench --site your.site.com migrate
bench build --app item_code_generation
bench restart
```

---

## Setup Checklist

### 1. Add SKU Codes to your Attribute Values
- Go to **Stock → Item Attribute**
- Open an attribute (e.g. *Size*)
- In the **Attribute Values** table you will see a **SKU Code** column
- Fill in the short code for each value (e.g. `SM` for Small)

### 2. Set the Template Item Code as the Pattern
- Open your template Item and check **Has Variants**
- Set the **Item Code** to the pattern e.g. `SHIRT{Size}{Color}`
- Placeholder names must match your Item Attribute names exactly (comparison is case-insensitive)
- The autocomplete dropdown will suggest attribute names as you type `{`

### 3. Create Variants Normally
- On the template Item, click **Create Variant**
- Select attribute values as usual
- The draft will show the correct generated item code immediately
- Hit Save — the variant's `item_code` and `name` will be set automatically

---

## License

GNU General Public License v3. See `license.txt`.

---

If this app saves you time, consider buying me a coffee!

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/grandpasam)
