# ufabc-pgc-wsrp

Undergraduate thesis project (UFABC) addressing the Workforce Scheduling and Routing Problem (WSRP) through optimization algorithms.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MFrizo/ufabc-pgc-wsrp/blob/main/notebooks/ufabc-pgc-wsrp.ipynb)

## Gurobi license

The pip release of `gurobipy` ships a size-limited license, too small for most models here. Run them under a [Web License Service (WLS)](https://support.gurobi.com/hc/en-us/articles/13232844297489-How-do-I-set-up-a-Web-License-Service-WLS-license) license instead.

- **Local:** save the `gurobi.lic` downloaded from the [Gurobi License Manager](https://license.gurobi.com/manager/licenses) to your home directory (`~/gurobi.lic`).
- **Google Colab:** open the Secrets panel (key icon on the left sidebar), add `WLSACCESSID`, `WLSSECRET` and `LICENSEID` with the values from your `gurobi.lic`, and enable notebook access for each one. The first notebook cell writes the license file from them before any solve.

Never commit `gurobi.lic` or its values to the repository.
