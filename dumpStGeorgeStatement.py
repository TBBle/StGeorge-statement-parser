#!/usr/bin/env python3

from PyPDF2TextExtractor import *
from operator import itemgetter
from PyPDF2 import PdfFileReader

import datetime
from locale import setlocale, LC_ALL, atof

#TODO: Date parsing, in its many-splendored forms...


def currencyToCents(currency):
    dollarStr, _, centStr = currency.partition(".")
    dollars = int("".join(dollarStr.split(",")))
    cents = int(centStr)
    return dollars * 100 + cents


def centsToCurrency(cents):
    return "${}".format(float(cents) / 100)


knownForeignCurrencies = ("USD", "EUR", "VND", "THB")


class Transaction(object):
    missing = []

    def __init__(self, date, detail, value, balance):
        self.date = date
        self.value = value
        self.balance = balance
        self.detail = detail

    def addDetail(self, detail):
        Transaction.missing.append(self.detail)
        self.detail = "{} {}".format(self.detail, detail)

    def __repr__(self):
        return "{}: {}: {}\t{}\t{}".format(
            self.__class__.__name__, self.date, self.detail,
            centsToCurrency(self.value), centsToCurrency(self.balance))


class VisaPurchase(Transaction):
    def __init__(self, date, realDate, value, balance):
        Transaction.__init__(self, date, None, value, balance)
        self.realDate = realDate
        self.effectiveDate = None

    def addDetail(self, detail):
        if detail.startswith("EFFECTIVE DATE"):
            assert self.effectiveDate is None, "Failed to add {} to {}".format(
                detail, self)
            self.effectiveDate = detail
        else:
            assert self.detail is None, "Failed to add {} to {}".format(detail,
                                                                        self)
            self.detail = detail

    def __repr__(self):
        return "{}: {}, Effective: {}, Statement: {}; {}\t{}\t{}".format(
            self.__class__.__name__, self.realDate, self.effectiveDate,
            self.date, self.detail, centsToCurrency(self.value),
            centsToCurrency(self.balance))


class VisaPurchaseForeign(Transaction):
    def __init__(self, date, realDate, value, balance):
        Transaction.__init__(self, date, None, value, balance)
        self.realDate = realDate
        self.foreignValue = None

    def addDetail(self, detail):
        for currPrefix in knownForeignCurrencies:
            if detail.startswith(currPrefix):
                assert self.foreignValue is None, "Failed to add {} to {}".format(
                    detail, self)
                self.foreignValue = detail
                return
        assert self.detail is None, "Failed to add {} to {}".format(detail,
                                                                    self)
        self.detail = detail

    def __repr__(self):
        return "{}: {}, Statement: {}; {}\t{} ({})\t{}".format(
            self.__class__.__name__, self.realDate, self.date, self.detail,
            self.foreignValue, centsToCurrency(self.value),
            centsToCurrency(self.balance))


class Credit(Transaction):
    def __init__(self, date, payer, value, balance):
        Transaction.__init__(self, date, payer, value, balance)
        self.note = None

    def addDetail(self, detail):
        assert self.note is None, "Failed to add {} to {}".format(detail, self)
        self.note = detail

    def __repr__(self):
        return "{}: {}: {} -- {}\t{}\t{}".format(
            self.__class__.__name__, self.date, self.detail, self.note,
            centsToCurrency(self.value), centsToCurrency(self.balance))


class VisaCredit(VisaPurchase):
    pass


class EftPosPurchase(Transaction):
    def __init__(self, date, detail, value, balance):
        Transaction.__init__(self, date, detail, value, balance)
        self.location = None

    def addDetail(self, detail):
        assert self.location is None, "Failed to add {} to {}".format(detail,
                                                                      self)
        self.location = detail


class AtmWithdrawal(EftPosPurchase):
    def __init__(self, date, detail, value, balance):
        EftPosPurchase.__init__(self, date, detail, value, balance)
        # Separate because 'detail' also notes if a Westpac ATM was used


class AtmWithdrawalForeign(AtmWithdrawal):
    def __init__(self, date, detail, value, balance):
        AtmWithdrawal.__init__(self, date, detail, value, balance)
        self.foreignValue = None

    def addDetail(self, detail):
        for currPrefix in knownForeignCurrencies:
            if detail.startswith(currPrefix):
                assert self.foreignValue is None, "Failed to add {} to {}".format(
                    detail, self)
                self.foreignValue = detail
                return
        AtmWithdrawal.addDetail(self, detail)


class AtmWithdrawalForeignFee(Transaction):
    def __init__(self, date, payer, value, balance):
        Transaction.__init__(self, date, payer, value, balance)
        # This is optional? This will be the last day of the month if the statement
        # wasn't processed, I guess.
        self.effectiveDate = date

    def addDetail(self, detail):
        assert detail.startswith("EFFECTIVE DATE")
        assert self.effectiveDate == self.date, "Failed to add {} to {}".format(
            detail, self)
        self.effectiveDate = detail

    def __repr__(self):
        return "{}: Effective: {}, Statement: {}; {}\t{}\t{}".format(
            self.__class__.__name__, self.effectiveDate, self.date,
            self.detail, centsToCurrency(self.value),
            centsToCurrency(self.balance))


class InternetBankingWithdrawal(Transaction):
    def __init__(self, date, payer, value, balance):
        Transaction.__init__(self, date, payer, value, balance)
        self.note = None

    def addDetail(self, detail):
        assert self.note is None, "Failed to add {} to {}".format(detail, self)
        self.note = detail

    def __repr__(self):
        return "{}: {}: {} -- {}\t{}\t{}".format(
            self.__class__.__name__, self.date, self.detail, self.note,
            centsToCurrency(self.value), centsToCurrency(self.balance))


creditPrefixes = [("VISA CREDIT", VisaCredit), ]

prefixes = [
    ("VISA PURCHASE O/SEAS", VisaPurchaseForeign),
    ("VISA PURCHASE", VisaPurchase),
    ("EFTPOS PURCHASE", EftPosPurchase),
    ("ATM WITHDRAWAL", AtmWithdrawal),
    ("VISA CASH ADVANCE", AtmWithdrawalForeign),
    ("INTERNET WITHDRAWAL", InternetBankingWithdrawal),
    ("O/SEAS CASH WITHDRAWAL FEE", AtmWithdrawalForeignFee),
]


class DirectDebit(Transaction):
    def __init__(self, date, payee, value, balance):
        Transaction.__init__(self, date, payee, value, balance)
        self.note = None

    def addDetail(self, detail):
        assert self.note is None, "Failed to add {} to {}".format(detail, self)
        self.note = detail

    def __repr__(self):
        return "{}: {}: {} -- {}\t{}\t{}".format(
            self.__class__.__name__, self.date, self.detail, self.note,
            centsToCurrency(self.value), centsToCurrency(self.balance))


directDebits = ["GMHBA"]


def addTransaction(date, detail, value, balance):
    if value > 0:
        for prefix, method in creditPrefixes:
            if detail.startswith(prefix):
                return method(date, detail, value, balance)
        return Credit(date, detail, value, balance)
    if detail in directDebits:
        # This is annoying. St George doesn't mark these in any useful way
        return DirectDebit(date, detail, value, balance)
    for prefix, method in prefixes:
        if detail.startswith(prefix):
            return method(date, detail, value, balance)

    return Transaction(date, detail, value, balance)


setlocale(LC_ALL, '')


def getTransactions(filename):
    pdf = PdfFileReader(open(filename, 'rb'))
    lastPageSeen = False
    transactions = []

    # TODO: First page has opening and closing balance

    for pageNum in range(pdf.numPages):
        #print("Page {}".format(pageNum + 1))
        page = pdf.getPage(pageNum)
        assert page.cropBox.lowerLeft == (0, 0)
        assert page.cropBox.upperRight == (596, 842)

        textBlocks = []

        pushDepth = 0
        for operation in pageOperations(page):
            if operation.__class__ is PopState:
                pushDepth -= 1
                continue

            if operation.__class__ is PushState:
                pushDepth += 1
                continue

            if pushDepth > 0:
                assert operation is not TextObject, "TextObject in pushed graphics state"
                continue

            if operation.__class__ is ConcatenateTransformationMatrix:
                # 0.6 scale in X and Y
                assert operation.matrixChange == [
                    [0.6, 0.0, 0.0], [0.0, 0.6, 0.0], [0.0, 0.0, 1.0]
                ], "unexpected matrixChange {}".format(operation.matrixChange)

# We're not in a pushed state, and we're in a known page layout, so we only
# care about TextObjects now.
            if operation.__class__ is not TextObject:
                continue

            textBlocks += operation.outputs

# We now have our collection of text renders, with page positions.
        linesDict = {}
        for (xPos, yPos), text in textBlocks:
            # Different fonts for some things appear to shift by a unit or two
            linePos = yPos
            if linePos + 1 in list(linesDict.keys()):
                linePos += 1
            elif linePos - 1 in list(linesDict.keys()):
                linePos -= 1
            elif linePos + 2 in list(linesDict.keys()):
                linePos += 2
            elif linePos - 2 in list(linesDict.keys()):
                linePos -= 2
            elif linePos not in list(linesDict.keys()):
                linesDict[linePos] = []
            linesDict[linePos].append((xPos, text))
            linesDict[linePos].sort(key=itemgetter(0))

        lines = sorted(
            list(linesDict.items()),
            key=itemgetter(0),
            reverse=True)

        #print("\n".join([str(l) for l in lines]))

        # Relevant things to find on each page
        # A "Statement Period", and the same Y and greater X will be the dates
        # "Transaction Details" (first page) or "Transaction Details continued" (later pages)
        #   This gives us the X of the left-hand column
        # The column headings: "Date", "Transaction Description", "Debit", "Credit", "Balance $"
        #   "Date" will line up with "Transaction Details", and these two columns are left-aligned.
        # The others are right-aligned, which is annoying
        # "OPENING BALANCE" and "CLOSING BALANCE" have a date, while
        # "SUB TOTAL CARRIED FORWARD FROM PREVIOUS PAGE" and "SUB TOTAL CARRIED FORWARD TO NEXT PAGE" do not.

        statementPeriodText = None
        dateColumn = None
        descriptionColumn = None
        debitColumn = None
        creditColumn = None
        balanceColumn = None
        runningBalance = None

        for lineRow, line in lines:
            if statementPeriodText is None:
                if line[0][1] == "Statement Period":
                    statementPeriodText = line[1][1]
                continue

            if dateColumn is None:
                if pageNum == 0 and line[0][
                        1] == "Transaction Details" or pageNum != 0 and line[
                            0][1] == "Transaction Details continued":
                    dateColumn = line[0][0]
                continue

            if descriptionColumn is None:
                if line[0][0] == dateColumn and line[0][1] == "Date":
                    assert line[1][1] == "Transaction Description"
                    descriptionColumn = line[1][0]
                    # The following columns are right-algned, so assuming 7 units per character, plus one more character
                    assert line[2][1] == "Debit"
                    debitColumn = line[2][0] + 42
                    assert line[3][1] == "Credit"
                    creditColumn = line[3][0] + 49
                    assert line[4][1] == "Balance $"
                    balanceColumn = line[4][0] + 81

                    continue

            dateText = None
            descText = None
            value = None
            balanceVal = None

            for column, text in line:
                if column == dateColumn:
                    assert dateText is None
                    dateText = text
                elif column == descriptionColumn:
                    assert descText is None
                    descText = text
                elif column < debitColumn:
                    assert value is None
                    value = -currencyToCents(text)
                elif column < creditColumn:
                    assert value is None
                    value = currencyToCents(text)
                else:
                    assert column < balanceColumn
                    assert balanceVal is None
                    balanceVal = currencyToCents(text)

            if dateText is None:
                assert value is None
                if descText == "SUB TOTAL CARRIED FORWARD FROM PREVIOUS PAGE":
                    # First line of transactions on second page onwards
                    assert pageNum > 0
                    assert runningBalance is None
                    runningBalance = balanceVal
                    continue
                elif descText == "SUB TOTAL CARRIED FORWARD TO NEXT PAGE":
                    # Last line of transactions on all pages except last
                    assert pageNum < pdf.numPages - 1
                    assert runningBalance == balanceVal
                    break
                else:
                    # Extra detail of previous transaction
                    assert balanceVal is None
                    assert len(transactions) > 0
                    transaction = transactions[-1]
                    transaction.addDetail(descText)
                continue

# TODO: For these two, check the date matches the statement period
            if descText == "OPENING BALANCE":
                assert value is None
                # First line of transactions on first page
                assert pageNum == 0
                assert runningBalance is None
                runningBalance = balanceVal
                continue
            elif descText == "CLOSING BALANCE":
                # Last line of transactions on last page
                assert runningBalance == balanceVal
                lastPageSeen = True
                break

# Must be a new transaction
            transactions.append(addTransaction(dateText, descText, value,
                                               balanceVal))
            runningBalance += value
            assert runningBalance == balanceVal, "Running balance is {} but calculated {}".format(
                centsToCurrency(runningBalance), centsToCurrency(balanceVal))

    assert len(
        GenericOperation.seenOperations) == 0, "Unknown operations in PDF: {}".format(
            GenericOperation.seenOperations)
    assert len(
        Transaction.missing) == 0, "Unhandled transaction types: {}".format(
            "\n".join(Transaction.missing))
    assert lastPageSeen

    return transactions

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("statement")
    args = parser.parse_args()
    transactions = getTransactions(args.statement)
    print(("\n".join([str(t) for t in transactions])))
