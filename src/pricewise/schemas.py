from pydantic import BaseModel, Field


class ProductQuery(BaseModel):
    """Input schema for the SearchProduct tool."""
    query: str = Field(description="The product search term")
    max_results: int = Field(default=3, ge=1, description="Maximum number of results to return")


class PriceComparisonQuery(BaseModel):
    """Input schema for the compare_prices tool."""
    product_name: str = Field(description="Name of the product to compare prices for")
    max_sources: int = Field(default=5, ge=1, description="Maximum number of price sources to return")


class ReviewQuery(BaseModel):
    """Input schema for the get_reviews tool."""
    product_name: str = Field(description="Name of the product to get reviews for")
    max_reviews: int = Field(default=3, ge=1, description="Maximum number of review sources to return")


class CouponQuery(BaseModel):
    """Input schema for the find_coupons tool."""
    product_or_retailer: str = Field(description="Product name or retailer to find coupons for")
    max_results: int = Field(default=5, ge=1, description="Maximum number of coupon sources to return")


class AvailabilityQuery(BaseModel):
    """Input schema for the check_availability tool."""
    product_name: str = Field(description="Name of the product to check availability for")
    max_sources: int = Field(default=5, ge=1, description="Maximum number of retailer sources to check")


class ProductResearchItem(BaseModel):
    """A single product to research in a multi-product delegation."""
    product_name: str = Field(description="Product name or category to research")
    budget: float | None = Field(default=None, description="Budget constraint for this item")


class DelegationQuery(BaseModel):
    """Input schema for the delegate_research tool."""
    products: list[ProductResearchItem] = Field(min_length=1, description="List of products to research in parallel")
    total_budget: float | None = Field(default=None, description="Overall budget constraint across all products")


class ProductSummary(BaseModel):
    """One product in a multi-product comparison."""
    product_name: str = Field(description="Name of the product")
    price: float = Field(ge=0, allow_inf_nan=False, description="Price of the product")
    currency: str = Field(default="USD", description="Currency code")
    average_rating: float | None = Field(default=None, description="Average rating from reviews")
    price_range: str | None = Field(default=None, description="Price range across retailers")
    pros: list[str] = Field(default_factory=list, description="Key advantages of this product")
    cons: list[str] = Field(default_factory=list, description="Key disadvantages of this product")


class Receipt(BaseModel):
    """Structured output schema for the agent's final response.

    For single-product queries, only the base fields are populated.
    For comparison queries, ``comparison_products`` holds the full list
    and ``comparison_summary`` provides an overall analysis.
    """
    product_name: str = Field(description="Name of the recommended product")
    price: float = Field(ge=0, allow_inf_nan=False, description="Price of the product")
    currency: str = Field(default="USD", description="Currency code")
    average_rating: float | None = Field(default=None, description="Average rating from reviews")
    price_range: str | None = Field(default=None, description="Price range across retailers, e.g. '$49 - $79'")
    recommendation_reason: str | None = Field(default=None, description="Why this product is recommended")
    comparison_products: list[ProductSummary] | None = Field(
        default=None,
        description="Other products in the comparison, if the user asked to compare multiple products",
    )
    comparison_summary: str | None = Field(
        default=None,
        description="Overall comparison analysis across all products",
    )


class BudgetItem(BaseModel):
    """A single item in a budget calculation."""
    name: str = Field(description="Product name")
    price: float = Field(ge=0, allow_inf_nan=False, description="Price of the product")


class BudgetQuery(BaseModel):
    """Input schema for the calculate_budget tool."""
    items: list[BudgetItem] = Field(description="List of items with name and price")
    tax_rate: float = Field(default=0.0, description="Tax rate as a decimal (e.g., 0.08 for 8%)")
    budget_limit: float | None = Field(default=None, description="Optional budget limit to check against")
