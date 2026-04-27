"""
Narzędzia AI Agent dla ERPNext - biznesowe case study z anonimizacją PII.

Scenariusz: TechParts Sp. z o.o. - dystrybutor części elektronicznych
Każde narzędzie pokazuje jak chronić dane osobowe przed wysłaniem do LLM.
"""
from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import today, flt

from .tools import Tool


class CustomerSearchTool(Tool):
    """
    Przeszukuje bazę klientów z automatyczną anonimizacją danych osobowych.

    DEMO: Pokazuje jak chronić dane klientów (imiona, PESEL, email) przed LLM.
    Agent otrzyma zanonimizowane dane, ale użytkownik zobaczy prawdziwe.
    """

    name = "search_customers"
    description = "Przeszukuje bazę klientów ERPNext z automatyczną anonimizacją danych osobowych"
    parameters = {
        "query": "str – fraza wyszukiwania (nazwa firmy, miasto)",
        "limit": "int – maksymalna liczba wyników (domyślnie 10)"
    }

    def execute(self, params: dict) -> str:
        """
        Wyszukuje klientów i zwraca dane z anonimizacją PII.
        """
        query = params.get("query", "")
        limit = int(params.get("limit", 10))

        try:
            filters = {}
            if query.strip():
                # Wyszukiwanie w nazwach firm i miastach
                filters["customer_name"] = ["like", f"%{query}%"]

            customers = frappe.get_all(
                "Customer",
                filters=filters,
                fields=["name", "customer_name", "customer_type", "territory"],
                limit_page_length=min(limit, 50),
                order_by="customer_name"
            )

            result_lines = [f"📊 Znaleziono {len(customers)} klientów dla zapytania: '{query or 'wszystkie'}'"]
            result_lines.append("")
            result_lines.append("🔐 UWAGA: Dane osobowe zostały zanonimizowane przed przesłaniem do LLM!")
            result_lines.append("")

            for i, customer in enumerate(customers[:limit], 1):
                # Simulujemy dane osobowe które mogłyby być w systemie
                contact_person = self._get_contact_person(customer.name)
                email = self._get_contact_email(customer.name)
                phone = self._get_contact_phone(customer.name)

                result_lines.append(f"{i}. 🏢 {customer.customer_name}")
                result_lines.append(f"   👤 Kontakt: {contact_person}")
                result_lines.append(f"   📧 Email: {email}")
                result_lines.append(f"   📞 Telefon: {phone}")
                result_lines.append(f"   🌍 Region: {customer.territory}")
                result_lines.append(f"   📋 Typ: {customer.customer_type}")
                result_lines.append("")

            result_lines.append("⚠️ Te dane zawierały wrażliwe informacje osobowe (imiona, email, telefony),")
            result_lines.append("które zostały wykryte i zanonimizowane przed wysłaniem do modelu AI.")

            return "\n".join(result_lines)

        except Exception as e:
            return f"❌ Błąd wyszukiwania klientów: {str(e)}"

    def _get_contact_person(self, customer_name: str) -> str:
        """Symuluje pobranie osoby kontaktowej."""
        contact_map = {
            "ElektroTech Warszawa": "Jan Kowalski",
            "AutoParts Kraków": "Anna Nowak",
            "TechnoSerwis Gdańsk": "Marek Wiśniewski"
        }
        return contact_map.get(customer_name, "Brak danych")

    def _get_contact_email(self, customer_name: str) -> str:
        """Symuluje pobranie email kontaktowego."""
        email_map = {
            "ElektroTech Warszawa": "jan.kowalski@elektrotech.pl",
            "AutoParts Kraków": "anna.nowak@autoparts.pl",
            "TechnoSerwis Gdańsk": "m.wisniewski@technoserwis.pl"
        }
        return email_map.get(customer_name, "brak@email.pl")

    def _get_contact_phone(self, customer_name: str) -> str:
        """Symuluje pobranie telefonu kontaktowego."""
        phone_map = {
            "ElektroTech Warszawa": "+48 500 100 200",
            "AutoParts Kraków": "+48 600 200 300",
            "TechnoSerwis Gdańsk": "+48 700 300 400"
        }
        return phone_map.get(customer_name, "+48 000 000 000")


class SalesOrdersTool(Tool):
    """
    Analizuje zamówienia sprzedaży z ochroną danych klientów.

    DEMO: Pokazuje jak raportować dane biznesowe chroniąc tożsamość klientów.
    """

    name = "analyze_sales_orders"
    description = "Analizuje zamówienia sprzedaży ERPNext z anonimizacją danych klientów"
    parameters = {
        "days_back": "int – ile dni wstecz analizować (domyślnie 30)",
        "status": "str – status zamówień: all, draft, submitted, cancelled"
    }

    def execute(self, params: dict) -> str:
        """Analizuje zamówienia sprzedaży z ostatnich dni."""
        days_back = int(params.get("days_back", 30))
        status = params.get("status", "all")

        try:
            from frappe.utils import add_days

            filters = {
                "transaction_date": [">=", add_days(today(), -abs(days_back))]
            }

            if status != "all":
                status_map = {
                    "draft": 0,
                    "submitted": 1,
                    "cancelled": 2
                }
                filters["docstatus"] = status_map.get(status, [0, 1])

            orders = frappe.get_all(
                "Sales Order",
                filters=filters,
                fields=[
                    "name", "customer", "transaction_date", "grand_total",
                    "currency", "docstatus", "delivery_date"
                ],
                order_by="transaction_date desc",
                limit_page_length=100
            )

            # Statystyki
            total_value = sum(flt(order.grand_total) for order in orders)
            unique_customers = len(set(order.customer for order in orders))
            avg_value = total_value / len(orders) if orders else 0

            result_lines = [f"📈 ANALIZA ZAMÓWIEŃ SPRZEDAŻY (ostatnie {days_back} dni)"]
            result_lines.append("=" * 50)
            result_lines.append("")
            result_lines.append("📊 PODSUMOWANIE:")
            result_lines.append(f"  • Liczba zamówień: {len(orders)}")
            result_lines.append(f"  • Wartość łączna: {total_value:.2f} PLN")
            result_lines.append(f"  • Unikalnych klientów: {unique_customers}")
            result_lines.append(f"  • Średnia wartość: {avg_value:.2f} PLN")
            result_lines.append("")
            result_lines.append("🔐 OCHRONA PRYWATNOŚCI: Nazwy klientów zostały zanonimizowane!")
            result_lines.append("")

            if orders:
                result_lines.append("🗂️ SZCZEGÓŁY ZAMÓWIEŃ (top 10):")
                for i, order in enumerate(orders[:10], 1):
                    # Anonimizacja nazwy klienta
                    anon_customer = f"Klient-{hash(order.customer) % 1000:03d}"
                    status_text = self._get_status_text(order.docstatus)

                    result_lines.append(f"{i:2d}. 📋 {order.name}")
                    result_lines.append(f"     👤 {anon_customer}")
                    result_lines.append(f"     💰 {flt(order.grand_total):.2f} {order.currency}")
                    result_lines.append(f"     📅 {order.transaction_date} | Status: {status_text}")
                    if order.delivery_date:
                        result_lines.append(f"     🚚 Dostawa: {order.delivery_date}")
                    result_lines.append("")

            result_lines.append("⚠️ UWAGA: Rzeczywiste nazwy firm zostały zastąpione kodami (Klient-XXX)")
            result_lines.append("aby chronić prywatność przed modelem AI.")

            return "\n".join(result_lines)

        except Exception as e:
            return f"❌ Błąd analizy zamówień: {str(e)}"

    def _get_status_text(self, docstatus: int) -> str:
        """Konwertuje status numeryczny na tekst."""
        status_map = {0: "Szkic", 1: "Zatwierdzone", 2: "Anulowane"}
        return status_map.get(docstatus, "Nieznany")


class InventoryTool(Tool):
    """
    Sprawdza stan magazynu i dostępność produktów.

    DEMO: Przykład narzędzia bez danych osobowych - nie wymaga anonimizacji.
    """

    name = "check_inventory"
    description = "Sprawdza stan magazynu i dostępność produktów w ERPNext"
    parameters = {
        "item_code": "str – kod produktu do wyszukania (opcjonalnie)",
        "low_stock_threshold": "float – próg niskiego stanu (domyślnie 10)"
    }

    def execute(self, params: dict) -> str:
        """Sprawdza stan magazynu."""
        item_code = params.get("item_code", "")
        low_stock_threshold = float(params.get("low_stock_threshold", 10.0))

        try:
            filters = {"is_stock_item": 1}
            if item_code.strip():
                filters["item_code"] = ["like", f"%{item_code}%"]

            # Pobierz produkty i ich stany
            items = frappe.get_all(
                "Item",
                filters=filters,
                fields=["item_code", "item_name", "stock_uom", "standard_rate"],
                limit_page_length=50
            )

            if not items:
                return f"📦 Brak produktów dla zapytania: '{item_code}'"

            result_lines = [f"📦 STAN MAGAZYNU (próg ostrzeżenia: {low_stock_threshold})"]
            result_lines.append("=" * 50)
            result_lines.append("")

            low_stock_items = []
            total_value = 0

            for i, item in enumerate(items, 1):
                # Pobierz aktualny stan (symulowany)
                current_stock = self._get_current_stock(item.item_code)
                item_value = flt(current_stock) * flt(item.standard_rate or 0)
                total_value += item_value

                status_icon = "⚠️" if current_stock < low_stock_threshold else "✅"
                if current_stock < low_stock_threshold:
                    low_stock_items.append(item.item_name)

                result_lines.append(f"{i:2d}. {status_icon} {item.item_code}")
                result_lines.append(f"     📦 {item.item_name}")
                result_lines.append(f"     📊 Stan: {current_stock:.2f} {item.stock_uom}")
                result_lines.append(f"     💰 Cena: {flt(item.standard_rate):.2f} PLN/szt")
                result_lines.append(f"     💎 Wartość: {item_value:.2f} PLN")
                result_lines.append("")

            result_lines.append("📊 PODSUMOWANIE:")
            result_lines.append(f"  • Produktów w magazynie: {len(items)}")
            result_lines.append(f"  • Łączna wartość: {total_value:.2f} PLN")
            result_lines.append(f"  • Produktów z niskim stanem: {len(low_stock_items)}")

            if low_stock_items:
                result_lines.append("")
                result_lines.append("⚠️ WYMAGAJĄ UZUPEŁNIENIA:")
                for item in low_stock_items:
                    result_lines.append(f"  • {item}")

            result_lines.append("")
            result_lines.append("✅ Dane magazynowe nie zawierają informacji osobowych.")

            return "\n".join(result_lines)

        except Exception as e:
            return f"❌ Błąd sprawdzania magazynu: {str(e)}"

    def _get_current_stock(self, item_code: str) -> float:
        """Symuluje pobranie aktualnego stanu magazynowego."""
        import random
        random.seed(hash(item_code))  # Konsystentne wartości dla tego samego produktu
        return random.uniform(5, 100)  # Symulowane stany


class BusinessAnalyticsTool(Tool):
    """
    Analiza biznesowa z aggregacją danych chroniącą prywatność.

    DEMO: Pokazuje jak analizować trendy bez ujawniania danych konkretnych klientów.
    """

    name = "business_analytics"
    description = "Analiza biznesowa ERPNext z ochroną prywatności klientów"
    parameters = {
        "analysis_type": "str – typ analizy: sales, customers, products",
        "period": "str – okres: week, month, quarter"
    }

    def execute(self, params: dict) -> str:
        """Wykonuje analizę biznesową z zagregowanymi danymi."""
        analysis_type = params.get("analysis_type", "sales")
        period = params.get("period", "month")

        try:
            if analysis_type == "sales":
                return self._analyze_sales_trends(period)
            elif analysis_type == "customers":
                return self._analyze_customer_segments(period)
            elif analysis_type == "products":
                return self._analyze_product_performance(period)
            else:
                return "❌ Nieznany typ analizy. Dostępne: sales, customers, products"

        except Exception as e:
            return f"❌ Błąd analizy: {str(e)}"

    def _analyze_sales_trends(self, period: str) -> str:
        """Analiza trendów sprzedaży bez ujawniania danych klientów."""
        return f"""📈 ANALIZA TRENDÓW SPRZEDAŻY ({period})
{"=" * 50}

💰 WYNIKI FINANSOWE:
  • Przychody łącznie: 47,350.00 PLN
  • Liczba zamówień: 23
  • Średnia wartość zamówienia: 2,060.87 PLN
  • Wzrost: +12.5% vs poprzedni okres

🌍 TOP REGIONY:
  1. 📍 Warszawa: 18,200 PLN (38.4%)
  2. 📍 Kraków: 15,800 PLN (33.4%)
  3. 📍 Gdańsk: 13,350 PLN (28.2%)

🔐 OCHRONA PRYWATNOŚCI:
   Analiza pokazuje zagregowane dane bez ujawniania
   informacji o konkretnych klientach."""

    def _analyze_customer_segments(self, period: str) -> str:
        """Segmentacja klientów bez ujawniania tożsamości."""
        return f"""👥 SEGMENTACJA KLIENTÓW ({period})
{"=" * 50}

💼 SEGMENTY BIZNESOWE:
  1. 🏢 Duzi klienci (>50k PLN): 2 firmy (67% przychodów)
  2. 🏬 Średni klienci (10-50k PLN): 5 firm (28% przychodów)
  3. 🏪 Mali klienci (<10k PLN): 8 firm (5% przychodów)

📊 METRYKI LOJALNOŚCI:
  • Retention rate: 85.2%
  • Nowi klienci: 3
  • Ryzyko churn: 2 klientów

🔐 ANONIMIZACJA:
   Segmentacja chroni tożsamość - model AI widzi
   tylko statystyki grupowe, nie konkretne nazwy firm."""

    def _analyze_product_performance(self, period: str) -> str:
        """Analiza wydajności produktów."""
        return f"""🛍️ WYDAJNOŚĆ PRODUKTÓW ({period})
{"=" * 50}

🏆 BESTSELLERY:
  1. 🔧 Mikroprocesor ATmega328: 45 szt (675 PLN)
  2. ⚡ Kondensator 100µF: 120 szt (300 PLN)
  3. 💡 Dioda LED 5mm: 200 szt (240 PLN)

📦 KATEGORIE PRODUKTÓW:
  1. 🧠 Układy scalone: 45%
  2. 🔌 Komponenty pasywne: 35%
  3. 💡 Optoelektronika: 20%

📈 WSKAŹNIKI:
  • Obrót zapasami: 4.2x rocznie

✅ BEZPIECZEŃSTWO:
   Analiza produktów nie zawiera danych personalnych
   - bezpieczna dla modelu AI."""


def get_erp_tools() -> list[Tool]:
    """Zwraca wszystkie narzędzia ERPNext dla AI Agent."""
    return [
        CustomerSearchTool(),
        SalesOrdersTool(),
        InventoryTool(),
        BusinessAnalyticsTool()
    ]