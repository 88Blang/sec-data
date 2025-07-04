import requests
from bs4 import BeautifulSoup
from io import StringIO
import pandas as pd
import warnings

headers = {"User-Agent": "personal use sec_data_repo@gmail.com"}

# TODO - sec_ticker_site - create class method
sec_ticker_site = "https://www.sec.gov/files/company_tickers.json"
company_url = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
secWebsite = "https://www.sec.gov/Archives/edgar/data"
filing_url = "https://www.sec.gov/Archives/edgar/data/{cik}/{accessionNumber}/{doc}"
statement_url = "https://www.sec.gov/Archives/edgar/data/{cik}/{accessionNumber}/R{statement_number}.htm"
# TODO - update map to include more for consolidated/unconsolidated case
statement_map = {"income_statement": 2, "balance_sheet": 4, "cash_flow": 6}


class secData:
    _cik_df = None

    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        if secData._cik_df is None:
            self.get_cik()

        self.find_cik()
        self.get_info()
        self.get_financials()
        self.get_img()

    def get_cik(self):
        try:
            cik_dict = self.get_url(url=sec_ticker_site, headers=headers)
            cik_df = pd.DataFrame.from_dict(cik_dict).T
            secData._cik_df = cik_df
        except:
            raise ValueError(f"Could Not Fetch CIK-Ticker Data.")

    def find_cik(self):
        try:
            cik_from_tick = secData._cik_df[secData._cik_df["ticker"] == self.ticker][
                "cik_str"
            ].values[0]
            self.cik = cik_from_tick
        except Exception as e:
            raise ValueError(f"Ticker '{self.ticker}' not found!, {e}")

    def get_info(self):
        self.url = company_url.format(cik=self.cik)
        sec_data = self.get_url(url=self.url, headers=headers)
        if sec_data:
            self.page = sec_data
            self.recent = sec_data["filings"].get("recent", "")
            self.name = sec_data.get("name", "")
            self.sec_ticker = sec_data.get("tickers", [""])[0]
            self.exchange = sec_data.get("exchanges", [""])[0]

            return True
        else:
            return False

    def get_financials(self):

        financials = []
        for line in range(0, len(self.recent["filingDate"])):
            form = self.recent["form"][line]
            accessionNumber = self.recent["accessionNumber"][line].replace("-", "")
            date = self.recent["filingDate"][line]
            doc = self.recent["primaryDocument"][line]
            form_url = filing_url.format(
                cik=str(self.cik), accessionNumber=accessionNumber, doc=doc
            )
            if form in ["10-Q", "10-K"]:
                financials.append(
                    {
                        "form_type": form,
                        "accessionNumber": accessionNumber,
                        "date": date,
                        "doc": doc,
                        "filing_url": form_url,
                    }
                )
            if len(financials) >= 10:
                break
        self.financials = financials
        return True

    def get_img(self):
        try:
            recent_filing = self.financials[0]
        except:
            warnings.warn(f"No Recent Filings for {self.ticker}", UserWarning)

        response = requests.get(recent_filing["filing_url"], headers=headers)
        soup = BeautifulSoup(response.content, features="xml")
        page_body = soup.body

        imgs = page_body.find_all("img")
        try:
            img_doc = imgs[0].get("src")  # Assuming first img is logo
            self.img_url = filing_url.format(
                cik=str(self.cik),
                accessionNumber=recent_filing["accessionNumber"],
                doc=img_doc,
            )
        except:
            self.img_url = None
            warnings.warn(f"Image not found for {self.ticker}.", UserWarning)

    def get_latest(self, statement_type: str = "income_statement"):
        """
        statement_type: income_statement, balance_sheet, cash_flow
        """
        # Get
        my_url = statement_url.format(
            cik=self.cik,
            accessionNumber=self.financials[0]["accessionNumber"],
            statement_number=statement_map[statement_type],
        )

        response = requests.get(my_url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, features="html.parser")
        else:
            raise RuntimeError(
                f"Request failed with status code {response.status_code}"
            )

        # Process
        tables = pd.read_html(StringIO(str(soup)))

        new_df = tables[0]
        # Drop Column index if MultiIndex
        if type(new_df.columns) == pd.core.indexes.multi.MultiIndex:
            new_df.columns = new_df.columns.droplevel(0)

            # Drop duplicate column
            if new_df.columns[1][:10] == new_df.columns[0][:10]:
                new_df = new_df.drop(new_df.columns[1], axis=1)
        # Rename Column
        df_name = self.name + " " + statement_type.title().replace("_", " ")
        new_df = new_df.rename(columns={new_df.columns[0]: df_name})
        # Drop NA rows
        new_df = new_df.dropna()
        return new_df

    # Helper method
    def get_url(self, url, headers={}):
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            raise RuntimeError(
                f"Request failed with status code {response.status_code}"
            )

    def get_dict(self):
        return {k: v for k, v in self.__dict__.items() if k != "filings"}
