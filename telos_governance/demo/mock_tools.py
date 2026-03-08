"""
Mock Tool Execution
====================
Simulated tool execution for the agentic governance demo.
Returns pre-defined outputs for common tool+request combinations.

This module provides realistic-looking tool outputs so the demo
can show complete governance flows without requiring live database
connections, web access, or customer service backends.

IMPORTANT: All data is fictional and for demonstration purposes only.
"""


class MockToolExecutor:
    """Simulated tool execution for demonstration."""

    def __init__(self):
        self._mock_outputs = self._build_mock_database()
        self._scenario = None  # Active benchmark scenario (tool_name -> output)

    def set_scenario(self, tool_outputs: dict) -> None:
        """Set scenario-specific tool outputs for benchmark execution.

        Args:
            tool_outputs: Dict mapping tool_name to pre-defined output string.
                          When set, execute() returns these outputs instead of
                          pattern-matching the mock database.
        """
        self._scenario = dict(tool_outputs) if tool_outputs else None

    def clear_scenario(self) -> None:
        """Clear the active scenario, reverting to default mock behavior."""
        self._scenario = None

    def execute(self, tool_name: str, user_request: str, agent_type: str = "sql_analyst") -> str:
        """
        Execute a simulated tool and return mock output.

        Args:
            tool_name: Name of the tool to execute
            user_request: The user's original request
            agent_type: Which agent template is active

        Returns:
            str: Simulated tool output
        """
        # Scenario override: benchmark runner provides deterministic outputs
        if self._scenario and tool_name in self._scenario:
            return self._scenario[tool_name]

        key = (tool_name, agent_type)
        if key in self._mock_outputs:
            for pattern, output in self._mock_outputs[key]:
                if pattern.lower() in user_request.lower():
                    return output

        return self._generic_output(tool_name, user_request)

    def _build_mock_database(self):
        """Build the mock output database."""
        return {
            # ===========================================================
            # SQL AGENT TOOLS
            # ===========================================================
            ("sql_db_list_tables", "sql_analyst"): [
                ("tables", (
                    "Found 8 tables in database:\n"
                    "  - customers (12,847 rows)\n"
                    "  - orders (89,231 rows)\n"
                    "  - order_items (245,672 rows)\n"
                    "  - products (3,412 rows)\n"
                    "  - regions (12 rows)\n"
                    "  - employees (234 rows)\n"
                    "  - suppliers (89 rows)\n"
                    "  - inventory (3,412 rows)"
                )),
                ("database", (
                    "Found 8 tables in database:\n"
                    "  - customers (12,847 rows)\n"
                    "  - orders (89,231 rows)\n"
                    "  - order_items (245,672 rows)\n"
                    "  - products (3,412 rows)\n"
                    "  - regions (12 rows)\n"
                    "  - employees (234 rows)\n"
                    "  - suppliers (89 rows)\n"
                    "  - inventory (3,412 rows)"
                )),
                ("available", (
                    "Found 8 tables in database:\n"
                    "  - customers (12,847 rows)\n"
                    "  - orders (89,231 rows)\n"
                    "  - order_items (245,672 rows)\n"
                    "  - products (3,412 rows)\n"
                    "  - regions (12 rows)\n"
                    "  - employees (234 rows)\n"
                    "  - suppliers (89 rows)\n"
                    "  - inventory (3,412 rows)"
                )),
            ],
            ("sql_db_schema", "sql_analyst"): [
                ("customers", (
                    "Table: customers\n"
                    "Columns:\n"
                    "  customer_id    INTEGER  PRIMARY KEY\n"
                    "  name           VARCHAR(255)\n"
                    "  email          VARCHAR(255)  UNIQUE\n"
                    "  region_id      INTEGER  REFERENCES regions(region_id)\n"
                    "  created_at     TIMESTAMP\n"
                    "  lifetime_value DECIMAL(12,2)\n\n"
                    "Sample rows:\n"
                    "  | 1001 | Acme Corp       | procurement@acme.example.com    | 3 | 2023-01-15 | 142,350.00 |\n"
                    "  | 1002 | GlobalTech Inc  | orders@globaltech.example.com   | 1 | 2023-02-20 |  89,200.00 |\n"
                    "  | 1003 | Smith & Co      | billing@smithco.example.com     | 5 | 2023-03-10 |  67,800.00 |"
                )),
                ("orders", (
                    "Table: orders\n"
                    "Columns:\n"
                    "  order_id     INTEGER  PRIMARY KEY\n"
                    "  customer_id  INTEGER  REFERENCES customers(customer_id)\n"
                    "  order_date   DATE\n"
                    "  total_amount DECIMAL(12,2)\n"
                    "  status       VARCHAR(50)\n"
                    "  region_id    INTEGER  REFERENCES regions(region_id)\n\n"
                    "Sample rows:\n"
                    "  | 50001 | 1001 | 2025-10-15 | 12,450.00 | completed | 3 |\n"
                    "  | 50002 | 1002 | 2025-10-18 |  8,200.00 | completed | 1 |\n"
                    "  | 50003 | 1003 | 2025-11-02 |  3,150.00 | shipped   | 5 |"
                )),
                ("products", (
                    "Table: products\n"
                    "Columns:\n"
                    "  product_id   INTEGER  PRIMARY KEY\n"
                    "  name         VARCHAR(255)\n"
                    "  category     VARCHAR(100)\n"
                    "  unit_price   DECIMAL(10,2)\n"
                    "  supplier_id  INTEGER  REFERENCES suppliers(supplier_id)\n\n"
                    "Sample rows:\n"
                    "  | 2001 | Enterprise Widget Pro  | Hardware    | 249.99 | 12 |\n"
                    "  | 2002 | Cloud Analytics Suite  | Software    | 899.00 | 15 |\n"
                    "  | 2003 | Secure Gateway Module  | Networking  | 450.00 | 12 |"
                )),
            ],
            ("sql_db_query", "sql_analyst"): [
                ("revenue", (
                    "Query: SELECT r.name AS region, SUM(o.total_amount) AS revenue\n"
                    "       FROM orders o JOIN regions r ON o.region_id = r.region_id\n"
                    "       WHERE o.order_date BETWEEN '2025-10-01' AND '2025-12-31'\n"
                    "       GROUP BY r.name ORDER BY revenue DESC;\n\n"
                    "Results (5 rows):\n"
                    "  | North America | $2,847,320.00 |\n"
                    "  | Europe        | $1,923,450.00 |\n"
                    "  | Asia Pacific  | $1,456,780.00 |\n"
                    "  | Latin America |   $634,200.00 |\n"
                    "  | Middle East   |   $412,100.00 |"
                )),
                ("top", (
                    "Query: SELECT c.name, COUNT(o.order_id) AS order_count,\n"
                    "              SUM(o.total_amount) AS total_spent\n"
                    "       FROM customers c JOIN orders o ON c.customer_id = o.customer_id\n"
                    "       GROUP BY c.name ORDER BY order_count DESC LIMIT 10;\n\n"
                    "Results (10 rows):\n"
                    "  | Acme Corp        | 147 | $142,350.00 |\n"
                    "  | GlobalTech Inc   | 124 |  $89,200.00 |\n"
                    "  | MegaRetail LLC   | 118 |  $78,450.00 |\n"
                    "  | DataDriven Co    |  95 |  $71,200.00 |\n"
                    "  | Smith & Co       |  89 |  $67,800.00 |\n"
                    "  | Pacific Trading  |  82 |  $54,300.00 |\n"
                    "  | Nordic Systems   |  76 |  $48,900.00 |\n"
                    "  | Alpine Group     |  71 |  $45,200.00 |\n"
                    "  | Coastal Imports  |  68 |  $42,100.00 |\n"
                    "  | Summit Partners  |  65 |  $39,800.00 |"
                )),
                ("select", (
                    "Query executed successfully.\n\n"
                    "Results (3 rows):\n"
                    "  | 50001 | 2025-10-15 | 12,450.00 | completed |\n"
                    "  | 50002 | 2025-10-18 |  8,200.00 | completed |\n"
                    "  | 50003 | 2025-11-02 |  3,150.00 | shipped   |"
                )),
            ],
            ("sql_db_query_checker", "sql_analyst"): [
                ("syntax", (
                    "Query validation result: VALID\n\n"
                    "The query uses correct PostgreSQL syntax. No issues detected.\n"
                    "Estimated execution: < 1 second (indexed columns used)"
                )),
                ("error", (
                    "Query validation result: WARNING\n\n"
                    "Potential issue: Missing GROUP BY clause for aggregation.\n"
                    "Suggestion: Add GROUP BY for non-aggregated columns."
                )),
                ("check", (
                    "Query validation result: VALID\n\n"
                    "The query uses correct PostgreSQL syntax. No issues detected.\n"
                    "Estimated execution: < 1 second (indexed columns used)"
                )),
            ],

            # ===========================================================
            # RESEARCH AGENT TOOLS
            # ===========================================================
            ("web_search", "research_assistant"): [
                ("ai governance", (
                    "Search results for 'AI governance principal-agent theory':\n\n"
                    "1. 'Principal-Agent Problems in AI Alignment' - ArXiv 2025\n"
                    "   Authors: Chen, Williams, et al.\n"
                    "   Summary: Formal framework applying P-A theory to LLM oversight.\n\n"
                    "2. 'Governance Frameworks for Autonomous AI Systems' - Nature Machine Intelligence\n"
                    "   Authors: Patel, Nakamura, et al.\n"
                    "   Summary: Survey of runtime governance approaches for agentic AI.\n\n"
                    "3. 'EU AI Act Compliance Through Runtime Monitoring' - AAAI 2025\n"
                    "   Authors: Muller, Johansson, et al.\n"
                    "   Summary: Technical requirements for Article 72 post-market monitoring."
                )),
                ("eu ai act", (
                    "Search results for 'EU AI Act Article 72':\n\n"
                    "1. 'EU AI Act - Full Text' - Official Journal of the European Union\n"
                    "   Article 72: Post-market monitoring by providers of high-risk AI systems\n"
                    "   Effective: August 2026\n\n"
                    "2. 'Article 72 Compliance Guide' - EU Digital Policy Center\n"
                    "   Summary: Providers must establish post-market monitoring systems\n"
                    "   proportionate to the nature of the AI technology and risks.\n\n"
                    "3. 'Runtime Monitoring Requirements Under the AI Act' - Tech Policy Press\n"
                    "   Summary: Analysis of ongoing monitoring obligations vs deploy-time testing."
                )),
                ("papers", (
                    "Search results (12 results found):\n\n"
                    "1. Most relevant paper found matching your query.\n"
                    "   Source: Academic database\n"
                    "   Relevance: High\n\n"
                    "2. Related work from adjacent research area.\n"
                    "   Source: Pre-print server\n"
                    "   Relevance: Medium\n\n"
                    "3. Survey paper covering the broader topic.\n"
                    "   Source: Conference proceedings\n"
                    "   Relevance: Medium"
                )),
            ],
            ("wikipedia", "research_assistant"): [
                ("cosine similarity", (
                    "Wikipedia: Cosine Similarity\n\n"
                    "Cosine similarity measures the cosine of the angle between two non-zero\n"
                    "vectors in an inner product space. It is defined as:\n\n"
                    "  similarity = (A . B) / (||A|| * ||B||)\n\n"
                    "Values range from -1 (exactly opposite) to 1 (exactly the same),\n"
                    "with 0 indicating orthogonality (decorrelation). In text analysis,\n"
                    "cosine similarity is widely used to measure document similarity by\n"
                    "comparing their vector representations in embedding space.\n\n"
                    "Applications: information retrieval, text mining, recommendation systems,\n"
                    "natural language processing, and AI alignment measurement."
                )),
                ("principal-agent", (
                    "Wikipedia: Principal-Agent Problem\n\n"
                    "The principal-agent problem occurs when one entity (the agent) is able to\n"
                    "make decisions on behalf of another entity (the principal). The problem\n"
                    "arises when the agent is motivated to act in their own interests rather\n"
                    "than those of the principal.\n\n"
                    "In AI systems, this maps to the alignment problem: the AI agent may\n"
                    "pursue objectives that diverge from the human principal's stated goals,\n"
                    "particularly in multi-step agentic tasks where oversight is limited."
                )),
                ("wikipedia", (
                    "Wikipedia article retrieved successfully.\n\n"
                    "The article provides a comprehensive overview of the topic with\n"
                    "historical context, key concepts, and references to primary sources."
                )),
            ],
            ("calculator", "research_assistant"): [
                ("statistical significance", (
                    "Statistical Analysis:\n\n"
                    "  p-value: 0.03\n"
                    "  Sample size (n): 150\n"
                    "  Significance level (alpha): 0.05\n\n"
                    "Result: STATISTICALLY SIGNIFICANT\n"
                    "  p (0.03) < alpha (0.05)\n\n"
                    "The result is statistically significant at the 5% level.\n"
                    "With n=150, the study has adequate power for medium effect sizes.\n"
                    "Note: Statistical significance does not imply practical significance."
                )),
                ("calculate", (
                    "Calculation complete.\n\n"
                    "  Result: See output below\n"
                    "  Precision: 6 decimal places\n"
                    "  Method: Standard numerical computation"
                )),
            ],
            ("summarize", "research_assistant"): [
                ("summarize", (
                    "Summary of provided text:\n\n"
                    "Key findings:\n"
                    "  1. Primary conclusion supported by evidence presented\n"
                    "  2. Secondary findings consistent with existing literature\n"
                    "  3. Limitations acknowledged by authors\n\n"
                    "Methodology: Quantitative analysis with appropriate controls.\n"
                    "Sample: Adequate for stated conclusions.\n"
                    "Implications: Results suggest further investigation warranted."
                )),
                ("findings", (
                    "Summary of key findings:\n\n"
                    "  1. The study establishes a significant relationship between\n"
                    "     the primary variables of interest.\n"
                    "  2. Effect sizes are moderate and practically meaningful.\n"
                    "  3. Results replicate across the tested conditions.\n\n"
                    "Confidence: High (based on methodology and sample size)."
                )),
            ],

            # ===========================================================
            # CUSTOMER SERVICE TOOLS
            # ===========================================================
            ("lookup_order", "customer_service"): [
                ("12345", (
                    "Order #12345\n"
                    "  Customer: Jane Smith\n"
                    "  Date: 2025-12-15\n"
                    "  Status: IN TRANSIT\n"
                    "  Estimated delivery: 2026-02-10\n"
                    "  Items:\n"
                    "    - Enterprise Widget Pro (x2)  $499.98\n"
                    "    - Secure Gateway Module (x1)  $450.00\n"
                    "  Subtotal: $949.98\n"
                    "  Shipping: $12.99\n"
                    "  Total: $962.97\n"
                    "  Tracking: Available (carrier: FastShip Express)"
                )),
                ("order", (
                    "Order found.\n"
                    "  Status: PROCESSING\n"
                    "  Date: 2026-01-28\n"
                    "  Items: 3 items\n"
                    "  Total: $1,247.50\n"
                    "  Estimated delivery: 2026-02-14"
                )),
                ("status", (
                    "Order found.\n"
                    "  Status: SHIPPED\n"
                    "  Last update: 2026-02-05\n"
                    "  Location: Regional distribution center\n"
                    "  Estimated delivery: 2026-02-09"
                )),
            ],
            ("process_refund", "customer_service"): [
                ("refund", (
                    "Refund Assessment:\n"
                    "  Order eligible for refund: YES\n"
                    "  Refund amount: $962.97\n"
                    "  Refund method: Original payment method\n"
                    "  Processing time: 5-7 business days\n\n"
                    "Note: Refund amount is within the $500 auto-approval limit.\n"
                    "Status: PENDING CONFIRMATION\n"
                    "Please confirm with customer before processing."
                )),
                ("damaged", (
                    "Damage Claim Assessment:\n"
                    "  Claim type: Damaged in transit\n"
                    "  Eligible for replacement: YES\n"
                    "  Eligible for refund: YES\n"
                    "  Recommended action: Full refund + replacement shipment\n\n"
                    "Status: PENDING CONFIRMATION\n"
                    "Please confirm preferred resolution with customer."
                )),
                ("return", (
                    "Return Assessment:\n"
                    "  Return window: Within 30-day policy\n"
                    "  Item condition: Must be unused and in original packaging\n"
                    "  Return shipping: Prepaid label will be provided\n"
                    "  Refund timeline: 5-7 business days after receipt\n\n"
                    "Status: PENDING CUSTOMER ACTION"
                )),
            ],
            ("search_faq", "customer_service"): [
                ("return policy", (
                    "FAQ: Return Policy\n\n"
                    "We accept returns within 30 days of delivery for most items.\n"
                    "Electronics must be returned within 15 days and in original packaging.\n"
                    "Personalized or custom items are non-returnable.\n\n"
                    "To initiate a return:\n"
                    "  1. Contact customer service with your order number\n"
                    "  2. Receive a prepaid return shipping label\n"
                    "  3. Ship the item within 7 days\n"
                    "  4. Refund processed within 5-7 business days of receipt"
                )),
                ("warranty", (
                    "FAQ: Product Warranties\n\n"
                    "Standard warranty: 1 year from date of purchase.\n"
                    "Extended warranty: Available for purchase (2 or 3 year options).\n\n"
                    "Coverage includes:\n"
                    "  - Manufacturing defects\n"
                    "  - Component failures under normal use\n"
                    "  - Software issues (for applicable products)\n\n"
                    "Not covered:\n"
                    "  - Physical damage from misuse\n"
                    "  - Water damage\n"
                    "  - Unauthorized modifications"
                )),
                ("shipping", (
                    "FAQ: Shipping Information\n\n"
                    "Standard shipping: 5-7 business days ($12.99)\n"
                    "Express shipping: 2-3 business days ($24.99)\n"
                    "Overnight shipping: Next business day ($49.99)\n\n"
                    "Free standard shipping on orders over $100.\n"
                    "All orders include tracking information via email."
                )),
            ],
            ("escalate_to_human", "customer_service"): [
                ("manager", (
                    "Escalation initiated.\n"
                    "  Priority: HIGH\n"
                    "  Reason: Customer requested supervisor\n"
                    "  Queue position: 2\n"
                    "  Estimated wait: 3-5 minutes\n\n"
                    "A supervisor has been notified and will join this conversation shortly.\n"
                    "All conversation history will be transferred."
                )),
                ("complaint", (
                    "Escalation initiated.\n"
                    "  Priority: HIGH\n"
                    "  Reason: Customer complaint\n"
                    "  Queue position: 1\n"
                    "  Estimated wait: 2-4 minutes\n\n"
                    "A specialist has been notified. Conversation context will be preserved."
                )),
                ("escalat", (
                    "Escalation initiated.\n"
                    "  Priority: NORMAL\n"
                    "  Queue position: 3\n"
                    "  Estimated wait: 5-8 minutes\n\n"
                    "A human agent has been notified and will be with you shortly."
                )),
            ],

            # ===========================================================
            # PROPERTY INTELLIGENCE TOOLS
            # ===========================================================
            ("property_lookup", "property_intel"): [
                ("742 evergreen", (
                    "Property Found: 742 Evergreen Terrace, Springfield IL 62704\n"
                    "  Parcel ID: 17-03-256-012\n"
                    "  Year Built: 1989\n"
                    "  Construction: Wood frame, 2-story residential\n"
                    "  Living Area: 2,200 sq ft\n"
                    "  Lot Size: 0.31 acres\n"
                    "  Last Imagery: 2025-09-14 (Vertical + Oblique)\n"
                    "  Prior Captures: 2025-04-22, 2024-10-08, 2024-05-15\n"
                    "  Building Permits: Roof replacement (2018-06), Deck addition (2021-03)"
                )),
                ("property", (
                    "Property Found.\n"
                    "  Parcel ID: 22-08-114-007\n"
                    "  Year Built: 2003\n"
                    "  Construction: Brick veneer, single-story residential\n"
                    "  Living Area: 1,850 sq ft\n"
                    "  Lot Size: 0.22 acres\n"
                    "  Last Imagery: 2025-11-03 (Vertical + Oblique)\n"
                    "  Building Permits: None on record since 2019"
                )),
                ("assess", (
                    "Property Found.\n"
                    "  Parcel ID: 09-15-302-019\n"
                    "  Year Built: 1997\n"
                    "  Construction: Wood frame, 1.5-story residential\n"
                    "  Living Area: 2,450 sq ft\n"
                    "  Lot Size: 0.28 acres\n"
                    "  Last Imagery: 2025-08-20 (Vertical + Oblique)\n"
                    "  Roof Age (AI-estimated): 2016 replacement (95% confidence)"
                )),
                ("commercial", (
                    "Property Found: 1500 Market Street, Philadelphia PA 19102\n"
                    "  Parcel ID: 88-02-0145-200\n"
                    "  Year Built: 2001\n"
                    "  Construction: Steel frame, Class A office\n"
                    "  Gross Area: 48,500 sq ft (4 stories)\n"
                    "  Lot Size: 0.42 acres\n"
                    "  Occupancy: Multi-tenant office\n"
                    "  Last Imagery: 2025-10-22 (Vertical + Oblique)\n"
                    "  Roof Type: Low-slope membrane (TPO)\n"
                    "  Roof-Mounted Equipment: 6 HVAC units, 2 satellite dishes\n"
                    "  Parking: Surface lot (45 spaces) + loading dock\n"
                    "  Building Permits: HVAC replacement (2024-03), facade repair (2023-11)"
                )),
                ("warehouse", (
                    "Property Found: 2200 Industrial Blvd, Memphis TN 38118\n"
                    "  Parcel ID: 45-12-0890-001\n"
                    "  Year Built: 1995\n"
                    "  Construction: Pre-engineered metal building\n"
                    "  Gross Area: 125,000 sq ft (single story, 28ft clear height)\n"
                    "  Lot Size: 4.2 acres\n"
                    "  Occupancy: Distribution warehouse\n"
                    "  Last Imagery: 2025-08-15 (Vertical + Oblique)\n"
                    "  Roof Type: Standing seam metal\n"
                    "  Roof-Mounted Equipment: 4 exhaust fans, 12 skylights\n"
                    "  Loading Docks: 8 dock-height doors, 2 drive-in doors\n"
                    "  Yard: Truck court, compactor area, fuel island\n"
                    "  Building Permits: Roof section replacement (2022-06)"
                )),
                ("retail", (
                    "Property Found: 450 Shopping Center Dr, Unit 12, Orlando FL 32801\n"
                    "  Parcel ID: 29-36-0220-012\n"
                    "  Year Built: 2008\n"
                    "  Construction: Concrete masonry (CMU), strip retail\n"
                    "  Gross Area: 8,200 sq ft (single story)\n"
                    "  Lot Size: 0.18 acres (shared parcel)\n"
                    "  Occupancy: Retail (restaurant tenant)\n"
                    "  Last Imagery: 2025-09-30 (Vertical + Oblique)\n"
                    "  Roof Type: Modified bitumen, flat\n"
                    "  Roof-Mounted Equipment: 3 RTU HVAC units, grease exhaust\n"
                    "  Shared Walls: Units 11 and 13 (fire-rated demising walls)\n"
                    "  Building Permits: Tenant improvement (2024-08)"
                )),
                ("multi-family", (
                    "Property Found: 850 Oak Park Ave, Units 1-12, Chicago IL 60302\n"
                    "  Parcel ID: 16-18-0412-000\n"
                    "  Year Built: 1962\n"
                    "  Construction: Brick masonry, 3-story walk-up\n"
                    "  Gross Area: 14,400 sq ft (12 units)\n"
                    "  Lot Size: 0.31 acres\n"
                    "  Occupancy: Multi-family residential (12 units)\n"
                    "  Last Imagery: 2025-07-18 (Vertical + Oblique)\n"
                    "  Roof Type: Modified bitumen over built-up, flat\n"
                    "  Roof-Mounted Equipment: 2 HVAC units, 4 vents, antenna\n"
                    "  Exterior: 3 entry points, fire escapes (E and W sides)\n"
                    "  Parking: Rear lot (8 spaces)\n"
                    "  Building Permits: Tuckpointing (2023-04), boiler replacement (2024-01)"
                )),
            ],
            ("aerial_image_retrieve", "property_intel"): [
                ("imagery", (
                    "Aerial Imagery Retrieved.\n"
                    "  Capture Date: 2025-09-14\n"
                    "  Resolution: 2.8 in/pixel (7.1 cm GSD)\n"
                    "  Views Available: Vertical (nadir), N/S/E/W oblique\n"
                    "  Coverage: Full parcel + 50m buffer\n"
                    "  Quality: Clear conditions, no cloud cover\n\n"
                    "AI Detections Overlaid:\n"
                    "  - Roof: Asphalt shingle, hip geometry, 6 facets\n"
                    "  - Objects: 1 chimney, 2 skylights, 1 A/C condenser\n"
                    "  - Yard: In-ground pool (fenced), 3 mature trees\n"
                    "  - Hazards: Tree overhang detected on NW roof facet\n"
                    "  - Solar: None detected"
                )),
                ("aerial", (
                    "Aerial Imagery Retrieved.\n"
                    "  Capture Date: 2025-11-03\n"
                    "  Resolution: 2.5 in/pixel (6.4 cm GSD)\n"
                    "  Views Available: Vertical (nadir), N/S/E/W oblique\n"
                    "  Coverage: Full parcel\n"
                    "  Quality: Clear conditions\n\n"
                    "AI Detections Overlaid:\n"
                    "  - Roof: Metal standing seam, gable geometry, 4 facets\n"
                    "  - Objects: 1 chimney, 2 vents\n"
                    "  - Yard: No pool, no trampoline, minimal vegetation\n"
                    "  - Hazards: None detected"
                )),
                ("latest", (
                    "Aerial Imagery Retrieved.\n"
                    "  Capture Date: 2025-08-20\n"
                    "  Resolution: 2.9 in/pixel (7.4 cm GSD)\n"
                    "  Views: Vertical + Oblique\n\n"
                    "  AI Detections: 47 features identified\n"
                    "  Flagged Items: 2 (see roof condition report)"
                )),
                ("compare", (
                    "Pre/Post Imagery Comparison:\n"
                    "  Pre-Event: 2025-04-22 capture\n"
                    "  Post-Event: 2025-09-14 capture\n\n"
                    "  Changes Detected:\n"
                    "  - Roof: New staining on SW facet (not present in April)\n"
                    "  - Roof: Temporary repair (tarp) on NE section — NEW\n"
                    "  - Vegetation: Tree overhang increased by ~4 ft\n"
                    "  - Structure: No structural changes detected\n\n"
                    "  Assessment: Roof condition has deteriorated between captures.\n"
                    "  Recommendation: Flag for underwriter review."
                )),
                ("commercial imagery", (
                    "Aerial Imagery Retrieved.\n"
                    "  Capture Date: 2025-10-22\n"
                    "  Resolution: 2.5 in/pixel (6.4 cm GSD)\n"
                    "  Views Available: Vertical (nadir), N/S/E/W oblique\n"
                    "  Coverage: Full parcel + 75m buffer\n"
                    "  Quality: Clear conditions, no cloud cover\n\n"
                    "AI Detections Overlaid:\n"
                    "  - Roof: Low-slope membrane (TPO), single plane\n"
                    "  - Equipment: 6 HVAC units, 2 satellite dishes, conduit runs\n"
                    "  - Parking: Surface lot (45 spaces delineated), loading dock\n"
                    "  - Structure: 4-story steel frame, curtain wall facade\n"
                    "  - Hazards: Ponding evidence near 2 drains (NW quadrant)\n"
                    "  - Adjacent: Public sidewalk, street parking, neighboring structure 12ft"
                )),
                ("warehouse imagery", (
                    "Aerial Imagery Retrieved.\n"
                    "  Capture Date: 2025-08-15\n"
                    "  Resolution: 2.8 in/pixel (7.1 cm GSD)\n"
                    "  Views Available: Vertical (nadir), N/S/E/W oblique\n"
                    "  Coverage: Full parcel + 100m buffer\n"
                    "  Quality: Clear conditions\n\n"
                    "AI Detections Overlaid:\n"
                    "  - Roof: Standing seam metal, single plane (125,000 sq ft)\n"
                    "  - Equipment: 4 exhaust fans, 12 skylights, roof access hatch\n"
                    "  - Loading: 8 dock doors (occupied: 3), 2 drive-in doors\n"
                    "  - Yard: Truck court (18 trailer spots), compactor, fuel island\n"
                    "  - Hazards: Rust staining near exhaust fans, 2 skylight seals degraded\n"
                    "  - Perimeter: Chain-link fencing, 2 access gates"
                )),
                ("multi-family imagery", (
                    "Aerial Imagery Retrieved.\n"
                    "  Capture Date: 2025-07-18\n"
                    "  Resolution: 2.6 in/pixel (6.6 cm GSD)\n"
                    "  Views Available: Vertical (nadir), N/S/E/W oblique\n"
                    "  Coverage: Full parcel + 50m buffer\n"
                    "  Quality: Clear conditions\n\n"
                    "AI Detections Overlaid:\n"
                    "  - Roof: Modified bitumen, flat, single plane\n"
                    "  - Equipment: 2 HVAC units, 4 vents, antenna mast\n"
                    "  - Structure: 3-story brick masonry, 3 entry points\n"
                    "  - Fire Safety: Fire escapes on E and W elevations\n"
                    "  - Parking: Rear lot (8 spaces), alley access\n"
                    "  - Hazards: Tuckpointing gaps on N elevation, parapet cracking"
                )),
            ],
            ("roof_condition_score", "property_intel"): [
                ("roof condition", (
                    "Roof Condition Assessment:\n"
                    "  Roof Spotlight Index (RSI): 62/100\n"
                    "  Confidence (RCCS): 0.89\n\n"
                    "  Material: Asphalt shingle (dominant)\n"
                    "  Geometry: Hip roof, 6 facets\n"
                    "  Estimated Pitch: 22 degrees\n"
                    "  Roof Area: 2,840 sq ft (pitch-adjusted)\n"
                    "  Estimated Roof Age: 7 years (2018 replacement)\n\n"
                    "  Condition Detections:\n"
                    "    - Staining: Moderate (SW facet, 18% of area)\n"
                    "    - Ponding: None detected\n"
                    "    - Missing Shingles: None detected\n"
                    "    - Worn Shingles: Minor (NE facet edge, 4% of area)\n"
                    "    - Temporary Repairs: None\n"
                    "    - Structural Damage: None\n\n"
                    "  Roof Objects: Chimney, 2 skylights, A/C condenser unit\n"
                    "  Tree Overhang: Detected on NW facet (recommend trimming)\n\n"
                    "  Risk Flag: MODERATE — Staining and early wear detected.\n"
                    "  Recommended Action: Acceptable for underwriting with note."
                )),
                ("assess", (
                    "Roof Condition Assessment:\n"
                    "  Roof Spotlight Index (RSI): 84/100\n"
                    "  Confidence (RCCS): 0.93\n\n"
                    "  Material: Metal standing seam\n"
                    "  Geometry: Gable, 4 facets\n"
                    "  Estimated Roof Age: 3 years\n\n"
                    "  Condition: Excellent\n"
                    "  Detections: No ponding, staining, damage, or repairs.\n\n"
                    "  Risk Flag: LOW — No condition concerns.\n"
                    "  Recommended Action: Straight-through processing eligible."
                )),
                ("commercial roof", (
                    "Roof Condition Assessment (Commercial):\n"
                    "  Roof Spotlight Index (RSI): 54/100\n"
                    "  Confidence (RCCS): 0.87\n\n"
                    "  Material: TPO membrane (low-slope)\n"
                    "  Geometry: Flat, single plane, 48,500 sq ft\n"
                    "  Estimated Roof Age: 12 years\n\n"
                    "  RCCS Per-Attribute Breakout:\n"
                    "    Ponding:           0.72 (ponding detected near 2 of 8 drains)\n"
                    "    Membrane Wear:     0.68 (UV degradation on south exposure)\n"
                    "    Flashing:          0.81 (perimeter flashing intact)\n"
                    "    Equipment Loading: 0.59 (6 HVAC units — concentrated loads)\n"
                    "    Drainage:          0.64 (2 drains partially blocked)\n\n"
                    "  Equipment Concentrated Load Points:\n"
                    "    - HVAC Unit 1 (NW): 2,400 lbs — membrane depression detected\n"
                    "    - HVAC Unit 4 (SE): 2,800 lbs — no visible distress\n"
                    "    - Satellite Dish 1: Penetration seal — intact\n\n"
                    "  Risk Flag: ELEVATED — Ponding and equipment loading concerns.\n"
                    "  Recommended Action: Flag for commercial underwriter review."
                )),
                ("flat roof", (
                    "Roof Condition Assessment (Flat/Low-Slope):\n"
                    "  Roof Spotlight Index (RSI): 48/100\n"
                    "  Confidence (RCCS): 0.85\n\n"
                    "  Material: Modified bitumen\n"
                    "  Geometry: Flat, single plane\n\n"
                    "  RCCS Per-Attribute Breakout:\n"
                    "    Ponding:           0.58 (multiple ponding areas detected)\n"
                    "    Membrane Wear:     0.62 (cracking in high-traffic areas)\n"
                    "    Flashing:          0.71 (minor flashing lift at parapet)\n"
                    "    Equipment Loading: 0.74 (3 RTU units, adequate support)\n"
                    "    Drainage:          0.52 (slope inadequate, 3 drains slow)\n\n"
                    "  Risk Flag: HIGH — Multiple drainage and wear concerns.\n"
                    "  Recommended Action: Require inspection before binding."
                )),
                ("membrane", (
                    "Roof Condition Assessment (Membrane):\n"
                    "  Roof Spotlight Index (RSI): 71/100\n"
                    "  Confidence (RCCS): 0.91\n\n"
                    "  Material: EPDM membrane\n"
                    "  Geometry: Low-slope, 2 sections\n\n"
                    "  RCCS Per-Attribute Breakout:\n"
                    "    Ponding:           0.85 (minimal ponding)\n"
                    "    Membrane Wear:     0.78 (seam integrity good)\n"
                    "    Flashing:          0.82 (counter-flashing secure)\n"
                    "    Equipment Loading: 0.69 (4 units, one with curb damage)\n"
                    "    Drainage:          0.79 (adequate slope maintained)\n\n"
                    "  Risk Flag: MODERATE — Monitor equipment curb at next capture.\n"
                    "  Recommended Action: Acceptable with condition note."
                )),
                ("warehouse roof", (
                    "Roof Condition Assessment (Warehouse):\n"
                    "  Roof Spotlight Index (RSI): 66/100\n"
                    "  Confidence (RCCS): 0.88\n\n"
                    "  Material: Standing seam metal\n"
                    "  Geometry: Low-slope, single plane, 125,000 sq ft\n"
                    "  Estimated Roof Age: 12 years (section replaced 2022)\n\n"
                    "  RCCS Per-Attribute Breakout:\n"
                    "    Ponding:           0.82 (minimal — metal drainage adequate)\n"
                    "    Panel Condition:   0.71 (rust staining near 2 exhaust fans)\n"
                    "    Flashing:          0.76 (ridge cap secure, eave flashing fair)\n"
                    "    Equipment Loading: 0.80 (exhaust fans on proper curbs)\n"
                    "    Skylight Seals:    0.58 (2 of 12 skylights show seal degradation)\n\n"
                    "  Risk Flag: MODERATE — Skylight seal degradation and rust.\n"
                    "  Recommended Action: Acceptable with maintenance recommendation."
                )),
                ("multi-family roof", (
                    "Roof Condition Assessment (Multi-Family):\n"
                    "  Roof Spotlight Index (RSI): 44/100\n"
                    "  Confidence (RCCS): 0.84\n\n"
                    "  Material: Modified bitumen over built-up\n"
                    "  Geometry: Flat, single plane, 4,800 sq ft\n"
                    "  Estimated Roof Age: 18 years\n\n"
                    "  RCCS Per-Attribute Breakout:\n"
                    "    Ponding:           0.48 (chronic ponding — 3 areas)\n"
                    "    Membrane Wear:     0.52 (alligatoring on south half)\n"
                    "    Flashing:          0.55 (parapet flashing lifted in 2 areas)\n"
                    "    Equipment Loading: 0.72 (2 HVAC units, adequate support)\n"
                    "    Drainage:          0.41 (internal drains — 2 of 4 slow)\n\n"
                    "  Risk Flag: HIGH — Age-related deterioration across multiple attributes.\n"
                    "  Recommended Action: Require inspection; consider roof age surcharge."
                )),
            ],
            ("peril_risk_score", "property_intel"): [
                ("hail", (
                    "Peril Risk Assessment:\n\n"
                    "  Hail Vulnerability Score: 72/100 (ELEVATED)\n"
                    "    - Roof material (asphalt shingle): Higher susceptibility\n"
                    "    - Regional hail frequency: Above average (Zone 3)\n"
                    "    - Hail Claim Predictor: 8.4x baseline likelihood\n"
                    "    - Filing status: Approved in 27 jurisdictions (Milliman)\n\n"
                    "  Wind Vulnerability Score: 45/100 (MODERATE)\n"
                    "    - Hip roof geometry: Good wind resistance\n"
                    "    - Tree proximity: 2 trees within 15 ft\n\n"
                    "  Wildfire Survivability: 88/100 (LOW RISK)\n"
                    "    - Defensible space: Adequate\n"
                    "    - Vegetation clearance: Meets guidelines\n\n"
                    "  Composite Peril Score: 58/100\n"
                    "  Primary Risk Driver: Hail exposure"
                )),
                ("wind", (
                    "Peril Risk Assessment:\n\n"
                    "  Wind Vulnerability Score: 67/100 (ELEVATED)\n"
                    "    - Gable roof end: Higher wind uplift risk\n"
                    "    - Regional wind exposure: Coastal zone\n\n"
                    "  Hail Vulnerability Score: 31/100 (LOW)\n"
                    "    - Metal roof: High impact resistance\n\n"
                    "  Composite Peril Score: 44/100\n"
                    "  Primary Risk Driver: Wind exposure (coastal)"
                )),
                ("wildfire", (
                    "Peril Risk Assessment:\n\n"
                    "  Wildfire Survivability: 42/100 (ELEVATED RISK)\n"
                    "    - Vegetation encroachment: Within 5 ft of structure\n"
                    "    - Defensible space: DOES NOT MEET guidelines\n"
                    "    - Adjacent wildland: Yes (within 300 ft)\n\n"
                    "  Recommended Action: Flag for inspection. Request\n"
                    "  vegetation clearance before binding."
                )),
                ("peril", (
                    "Peril Risk Assessment:\n\n"
                    "  Hail: 55/100 (MODERATE)\n"
                    "  Wind: 45/100 (MODERATE)\n"
                    "  Wildfire: 88/100 (LOW RISK)\n"
                    "  Hurricane: N/A (inland property)\n\n"
                    "  Composite Peril Score: 51/100\n"
                    "  No elevated risk drivers detected."
                )),
                ("commercial peril", (
                    "Peril Risk Assessment (Commercial):\n\n"
                    "  Wind Vulnerability Score: 78/100 (HIGH)\n"
                    "    - Flat/low-slope roof: Higher uplift risk at perimeter and corners\n"
                    "    - Large roof area (48,500 sq ft): Greater wind exposure surface\n"
                    "    - Equipment anchoring: 6 HVAC units create uplift weak points\n"
                    "    - Regional wind zone: Moderate (Zone 2)\n\n"
                    "  Hail Vulnerability Score: 65/100 (ELEVATED)\n"
                    "    - TPO membrane: Moderate impact resistance (FM 4473 rated)\n"
                    "    - Equipment damage risk: Condenser coils exposed\n"
                    "    - Skylight/satellite dish vulnerability: 4 penetration points\n\n"
                    "  Equipment Damage Risk: 71/100 (ELEVATED)\n"
                    "    - 6 HVAC units ($180K replacement value)\n"
                    "    - 2 satellite dishes ($12K replacement value)\n"
                    "    - Roof-mounted conduit and piping\n\n"
                    "  Composite Peril Score: 68/100\n"
                    "  Primary Risk Drivers: Wind uplift (flat roof) + equipment exposure"
                )),
                ("flat roof peril", (
                    "Peril Risk Assessment (Flat Roof):\n\n"
                    "  Wind Vulnerability Score: 82/100 (HIGH)\n"
                    "    - Flat geometry: Maximum uplift risk at perimeter zones\n"
                    "    - Corner zones (ASCE 7): 3x field pressure\n"
                    "    - Membrane adhesion: Age-dependent concern\n\n"
                    "  Hail Vulnerability Score: 58/100 (MODERATE)\n"
                    "    - Modified bitumen: Fair impact resistance\n"
                    "    - Gravel surfacing: Some hail mitigation\n\n"
                    "  Composite Peril Score: 62/100\n"
                    "  Primary Risk Driver: Wind uplift on flat membrane"
                )),
                ("warehouse peril", (
                    "Peril Risk Assessment (Warehouse):\n\n"
                    "  Wind Vulnerability Score: 74/100 (ELEVATED)\n"
                    "    - Large metal panel area: Wind-driven rain infiltration risk\n"
                    "    - Dock doors: 10 potential breach points\n"
                    "    - Clear height (28 ft): Internal pressurization concern\n\n"
                    "  Hail Vulnerability Score: 42/100 (MODERATE)\n"
                    "    - Standing seam metal: Good impact resistance\n"
                    "    - Skylight vulnerability: 12 skylights exposed\n\n"
                    "  Composite Peril Score: 55/100\n"
                    "  Primary Risk Driver: Wind (dock doors + metal panel uplift)"
                )),
                ("multi-family peril", (
                    "Peril Risk Assessment (Multi-Family):\n\n"
                    "  Wind Vulnerability Score: 61/100 (ELEVATED)\n"
                    "    - Flat roof: Uplift risk at parapet edges\n"
                    "    - Parapet condition: Compromised in 2 areas\n"
                    "    - Fire escape attachment: Additional wind load points\n\n"
                    "  Hail Vulnerability Score: 68/100 (ELEVATED)\n"
                    "    - Modified bitumen (aged): Reduced impact resistance\n"
                    "    - Roof-mounted equipment: 2 HVAC units exposed\n\n"
                    "  Composite Peril Score: 59/100\n"
                    "  Primary Risk Drivers: Hail on aged membrane + wind at parapets"
                )),
            ],
            ("generate_property_report", "property_intel"): [
                ("report", (
                    "Property Intelligence Report Generated.\n\n"
                    "  Report ID: PIR-2025-09-14-256012\n"
                    "  Property: 742 Evergreen Terrace, Springfield IL\n"
                    "  Generated: 2026-02-11\n\n"
                    "  SUMMARY:\n"
                    "  - RSI Score: 62/100 (Moderate condition)\n"
                    "  - Roof Age: 7 years (2018 replacement confirmed via permits)\n"
                    "  - Hail Risk: ELEVATED (72/100)\n"
                    "  - Wind Risk: Moderate (45/100)\n"
                    "  - Wildfire Risk: Low (88/100 survivability)\n"
                    "  - Hazards: Tree overhang (NW facet), in-ground pool (fenced)\n\n"
                    "  AI DETECTIONS (47 features):\n"
                    "  - Roof: Asphalt shingle, hip, 6 facets, 2,840 sq ft\n"
                    "  - Condition: Moderate staining (SW), minor wear (NE edge)\n"
                    "  - Objects: Chimney, 2 skylights, A/C unit\n"
                    "  - Property: Pool (fenced), 3 mature trees, no trampoline\n\n"
                    "  UNDERWRITING FLAGS:\n"
                    "  1. Hail vulnerability elevated — consider hail deductible\n"
                    "  2. Tree overhang on NW facet — recommend trimming notice\n"
                    "  3. Roof staining progression — monitor at next renewal\n\n"
                    "  CONFIDENCE: 0.89 (RCCS) | All scores pre-filed in 27 jurisdictions\n"
                    "  DECISION SUPPORT ONLY — Binding requires licensed underwriter review.\n\n"
                    "  Report exported: PDF + JSON available via API\n"
                    "  MapBrowser link: [imagery verification available]"
                )),
                ("underwriting", (
                    "Property Intelligence Report Generated.\n\n"
                    "  SUMMARY: Property eligible for straight-through processing.\n"
                    "  RSI: 84/100 | Peril Composite: 44/100\n"
                    "  No flags triggered. Report attached."
                )),
                ("generate", (
                    "Property Intelligence Report Generated.\n\n"
                    "  Report includes: Annotated imagery, AI detections,\n"
                    "  RSI score, peril vulnerability scores, and flagged items.\n"
                    "  Format: PDF + JSON\n"
                    "  DECISION SUPPORT ONLY."
                )),
                ("commercial report", (
                    "Commercial Property Intelligence Report Generated.\n\n"
                    "  Report ID: PIR-2025-10-22-0145200\n"
                    "  Property: 1500 Market Street, Philadelphia PA\n"
                    "  Property Type: Commercial (Class A Office)\n"
                    "  Generated: 2026-02-11\n\n"
                    "  SUMMARY:\n"
                    "  - RSI Score: 54/100 (Elevated condition concerns)\n"
                    "  - Roof Age: 12 years (TPO membrane)\n"
                    "  - Wind Risk: HIGH (78/100 — flat roof uplift)\n"
                    "  - Hail Risk: ELEVATED (65/100 — membrane + equipment)\n"
                    "  - Equipment Exposure: $192K replacement value on roof\n\n"
                    "  AI DETECTIONS (62 features):\n"
                    "  - Roof: TPO membrane, flat, 48,500 sq ft\n"
                    "  - Equipment: 6 HVAC units, 2 satellite dishes, conduit\n"
                    "  - Condition: Ponding (2 drains), membrane UV degradation\n"
                    "  - Parking: 45-space lot, loading dock\n\n"
                    "  UNDERWRITING FLAGS:\n"
                    "  1. Wind uplift risk elevated — flat roof + large area\n"
                    "  2. Ponding near 2 drains — drainage maintenance needed\n"
                    "  3. Equipment concentrated loads — membrane depression at Unit 1\n"
                    "  4. Roof age approaching mid-life — plan for replacement\n\n"
                    "  CONFIDENCE: 0.87 (RCCS)\n"
                    "  DECISION SUPPORT ONLY — Binding requires licensed underwriter review.\n\n"
                    "  Report exported: PDF + JSON available via API"
                )),
                ("warehouse report", (
                    "Warehouse Property Intelligence Report Generated.\n\n"
                    "  Report ID: PIR-2025-08-15-0890001\n"
                    "  Property: 2200 Industrial Blvd, Memphis TN\n"
                    "  Property Type: Distribution Warehouse\n"
                    "  Generated: 2026-02-11\n\n"
                    "  SUMMARY:\n"
                    "  - RSI Score: 66/100 (Moderate condition)\n"
                    "  - Roof Area: 125,000 sq ft (standing seam metal)\n"
                    "  - Wind Risk: ELEVATED (74/100 — dock doors + panel uplift)\n"
                    "  - Hail Risk: MODERATE (42/100 — metal resistance)\n\n"
                    "  UNDERWRITING FLAGS:\n"
                    "  1. 2 skylight seals degraded — water infiltration risk\n"
                    "  2. Rust staining near exhaust fans\n"
                    "  3. 10 dock doors — wind breach vulnerability\n\n"
                    "  CONFIDENCE: 0.88 (RCCS)\n"
                    "  DECISION SUPPORT ONLY."
                )),
                ("multi-family report", (
                    "Multi-Family Property Intelligence Report Generated.\n\n"
                    "  Report ID: PIR-2025-07-18-0412000\n"
                    "  Property: 850 Oak Park Ave, Chicago IL\n"
                    "  Property Type: Multi-Family (12 units, 3-story)\n"
                    "  Generated: 2026-02-11\n\n"
                    "  SUMMARY:\n"
                    "  - RSI Score: 44/100 (High condition concerns)\n"
                    "  - Roof Age: 18 years (modified bitumen over built-up)\n"
                    "  - Hail Risk: ELEVATED (68/100 — aged membrane)\n"
                    "  - Wind Risk: ELEVATED (61/100 — compromised parapets)\n\n"
                    "  UNDERWRITING FLAGS:\n"
                    "  1. Chronic ponding — 3 areas, drainage inadequate\n"
                    "  2. Alligatoring on south half — membrane end-of-life\n"
                    "  3. Parapet flashing lifted — 2 areas\n"
                    "  4. Tuckpointing gaps on N elevation — moisture risk\n\n"
                    "  CONFIDENCE: 0.84 (RCCS)\n"
                    "  DECISION SUPPORT ONLY — Recommend inspection before binding."
                )),
            ],

            # ===========================================================
            # CIVIC SERVICES TOOLS
            # ===========================================================
            ("lookup_service", "civic_services"): [
                ("building permit", (
                    "Service Found: Building Permits\n"
                    "  Department: Community Development\n"
                    "  Description: Residential and commercial building permits\n"
                    "  Requirements:\n"
                    "    - Completed permit application form\n"
                    "    - Site plan / architectural drawings\n"
                    "    - Proof of property ownership or authorization\n"
                    "    - Application fee ($75-$500 depending on scope)\n"
                    "  Processing Time: 5-15 business days\n"
                    "  Hours: Mon-Fri 8:00 AM - 4:30 PM\n"
                    "  Contact: permits@city.example.gov | (555) 234-5678"
                )),
                ("business license", (
                    "Service Found: Business Licensing\n"
                    "  Department: Finance / Business Services\n"
                    "  Description: New business license application and renewal\n"
                    "  Requirements:\n"
                    "    - Completed business license application\n"
                    "    - State registration / EIN documentation\n"
                    "    - Zoning compliance verification\n"
                    "    - Annual fee ($50-$300 based on business type)\n"
                    "  Processing Time: 3-10 business days\n"
                    "  Hours: Mon-Fri 8:30 AM - 5:00 PM\n"
                    "  Contact: business@city.example.gov | (555) 234-5700"
                )),
                ("trash", (
                    "Service Found: Solid Waste & Recycling\n"
                    "  Department: Public Works\n"
                    "  Description: Residential trash, recycling, and yard waste collection\n"
                    "  Schedule: Weekly curbside pickup (varies by zone)\n"
                    "  Bulk Pickup: Available by appointment (max 3 items per request)\n"
                    "  Contact: publicworks@city.example.gov | (555) 234-5800"
                )),
                ("parking permit", (
                    "Service Found: Residential Parking Permits\n"
                    "  Department: Transportation\n"
                    "  Description: Annual residential parking permits for permit-restricted zones\n"
                    "  Requirements:\n"
                    "    - Proof of residency in permit zone\n"
                    "    - Vehicle registration\n"
                    "    - Annual fee ($25/vehicle, max 2 per household)\n"
                    "  Available Online: Yes — apply at parking.city.example.gov\n"
                    "  Processing Time: Same day (online) / 3-5 days (mail)\n"
                    "  Contact: parking@city.example.gov | (555) 234-5850"
                )),
            ],
            ("check_eligibility", "civic_services"): [
                ("utility assistance", (
                    "Eligibility Check: Low-Income Utility Assistance Program (LIUAP)\n\n"
                    "  General Eligibility Criteria:\n"
                    "    - Household income at or below 150% Federal Poverty Level\n"
                    "    - Resident of city for at least 6 months\n"
                    "    - Utility account in applicant's name or household member\n"
                    "    - Not currently receiving duplicate assistance\n\n"
                    "  2026 Income Thresholds (150% FPL):\n"
                    "    1 person:  $22,590   |  2 persons: $30,660\n"
                    "    3 persons: $38,730   |  4 persons: $46,800\n\n"
                    "  Required Documents:\n"
                    "    - Photo ID\n"
                    "    - Proof of income (last 30 days)\n"
                    "    - Current utility bill\n\n"
                    "  IMPORTANT: This is preliminary eligibility information only.\n"
                    "  Final eligibility is determined by program staff upon review\n"
                    "  of your complete application."
                )),
                ("senior", (
                    "Eligibility Check: Senior Services Programs\n\n"
                    "  General Eligibility Criteria:\n"
                    "    - Age 60 or older (some programs 65+)\n"
                    "    - City resident\n"
                    "    - Programs available regardless of income:\n"
                    "      * Senior center activities and classes\n"
                    "      * Transportation assistance (age 65+)\n"
                    "    - Income-based programs:\n"
                    "      * Meal delivery (at or below 200% FPL)\n"
                    "      * Property tax freeze (at or below 185% FPL)\n\n"
                    "  IMPORTANT: This is preliminary eligibility information only.\n"
                    "  Contact Senior Services at (555) 234-5900 for final determination."
                )),
                ("eligible", (
                    "Eligibility Screening Complete.\n\n"
                    "  Based on the general criteria for this program, you may\n"
                    "  be eligible. Please gather the required documents and\n"
                    "  submit a formal application for official determination.\n\n"
                    "  IMPORTANT: This is preliminary information only.\n"
                    "  Binding eligibility requires staff review."
                )),
            ],
            ("find_office_location", "civic_services"): [
                ("dmv", (
                    "Office Location: Department of Motor Vehicles\n"
                    "  Address: 200 Government Center Drive, Suite 110\n"
                    "  Hours: Mon-Fri 8:00 AM - 5:00 PM, Sat 9:00 AM - 1:00 PM\n"
                    "  Phone: (555) 234-6000\n\n"
                    "  Accessibility:\n"
                    "    - ADA compliant: Yes\n"
                    "    - Wheelchair accessible entrance: Front door\n"
                    "    - Parking: Free lot (15 ADA spaces)\n"
                    "    - Public transit: Bus routes 12, 45 (Government Center stop)\n\n"
                    "  Current Wait Time: ~35 minutes (appointments recommended)\n"
                    "  Online Services: License renewal, registration at dmv.state.example.gov"
                )),
                ("city hall", (
                    "Office Location: City Hall\n"
                    "  Address: 100 Main Street\n"
                    "  Hours: Mon-Fri 8:30 AM - 5:00 PM\n"
                    "  Phone: (555) 234-5000\n\n"
                    "  Departments on-site:\n"
                    "    - Mayor's Office (2nd floor)\n"
                    "    - City Clerk (1st floor)\n"
                    "    - Finance / Tax Payments (1st floor)\n"
                    "    - Community Development (3rd floor)\n\n"
                    "  Accessibility: ADA compliant, elevator, 8 ADA parking spaces\n"
                    "  Public Transit: Bus routes 5, 12, 22"
                )),
                ("office", (
                    "Office location found.\n"
                    "  See details above for address, hours, and accessibility information."
                )),
            ],
            ("search_policy", "civic_services"): [
                ("noise ordinance", (
                    "Policy Found: Municipal Noise Ordinance (Chapter 18, Section 18-201)\n\n"
                    "  Residential Areas:\n"
                    "    - Quiet hours: 10:00 PM - 7:00 AM (weekdays)\n"
                    "                   11:00 PM - 8:00 AM (weekends/holidays)\n"
                    "    - Construction: Permitted 7:00 AM - 6:00 PM (Mon-Sat only)\n"
                    "    - Maximum decibel level: 65 dB at property line (daytime)\n"
                    "                              55 dB at property line (nighttime)\n\n"
                    "  Exceptions: Emergency vehicles, city maintenance, permitted events\n"
                    "  Complaints: File at city.example.gov/noise or call (555) 234-5555\n\n"
                    "  Source: Municipal Code Chapter 18 (effective 2024-01-01)\n"
                    "  Note: This is a summary. Consult the full ordinance text for\n"
                    "  complete provisions or seek legal counsel for interpretation."
                )),
                ("zoning", (
                    "Policy Found: Zoning Regulations Summary\n\n"
                    "  Residential Zones: R-1 (single family), R-2 (duplex), R-3 (multi-family)\n"
                    "  Commercial Zones: C-1 (neighborhood), C-2 (general), C-3 (highway)\n"
                    "  Industrial Zones: I-1 (light), I-2 (heavy)\n\n"
                    "  Zoning Map: Available at planning.city.example.gov/zoning-map\n"
                    "  Variances: Apply through Board of Zoning Appeals\n\n"
                    "  Source: Municipal Zoning Code Title 12\n"
                    "  Note: This is a summary. Consult the full code or a licensed\n"
                    "  attorney for specific zoning questions."
                )),
                ("policy", (
                    "Policy search completed.\n"
                    "  Found relevant municipal policy documents.\n"
                    "  Note: Summaries provided for informational purposes only.\n"
                    "  Consult official sources for authoritative text."
                )),
            ],
            ("submit_service_request", "civic_services"): [
                ("pothole", (
                    "Service Request Submitted: Pothole Repair\n"
                    "  Request ID: SR-2026-02-12-04821\n"
                    "  Department: Public Works — Streets Division\n"
                    "  Priority: Standard (5-10 business day response)\n"
                    "  Status: RECEIVED\n\n"
                    "  Track your request at: city.example.gov/service-tracker\n"
                    "  Reference number: SR-2026-02-12-04821"
                )),
                ("streetlight", (
                    "Service Request Submitted: Streetlight Outage\n"
                    "  Request ID: SR-2026-02-12-04822\n"
                    "  Department: Public Works — Electrical\n"
                    "  Priority: Standard (3-7 business day response)\n"
                    "  Status: RECEIVED\n\n"
                    "  Track your request at: city.example.gov/service-tracker"
                )),
                ("report", (
                    "Service Request Submitted.\n"
                    "  Your request has been received and assigned to the\n"
                    "  appropriate department.\n"
                    "  Status: RECEIVED\n"
                    "  You will receive a confirmation email with tracking details."
                )),
            ],
            ("escalate_to_staff", "civic_services"): [
                ("complaint", (
                    "Escalation Initiated.\n"
                    "  Priority: HIGH\n"
                    "  Reason: Citizen complaint\n"
                    "  Department: Citizen Relations\n"
                    "  Queue Position: 2\n"
                    "  Estimated Response: Within 1 business day\n\n"
                    "  Your concern has been logged and a staff member will\n"
                    "  contact you. Reference: ESC-2026-02-12-0147"
                )),
                ("appeal", (
                    "Escalation Initiated.\n"
                    "  Priority: HIGH\n"
                    "  Reason: Appeal / reconsideration request\n"
                    "  Department: Administrative Hearings\n"
                    "  Estimated Response: Within 3 business days\n\n"
                    "  A hearing officer will review your case.\n"
                    "  Reference: ESC-2026-02-12-0148"
                )),
                ("staff", (
                    "Escalation Initiated.\n"
                    "  Priority: NORMAL\n"
                    "  A government staff member will follow up with you.\n"
                    "  Estimated Response: Within 2 business days"
                )),
            ],

            # ===========================================================
            # ITEL MATERIAL ANALYSIS TOOLS
            # ===========================================================
            ("request_material_sample", "property_intel"): [
                ("material sample", (
                    "ITEL Material Sample Request Initiated.\n"
                    "  Request ID: ITEL-2026-02-11-00847\n"
                    "  Property: 742 Evergreen Terrace, Springfield IL\n"
                    "  Sample Type: Roof material identification\n"
                    "  Damage Area: NW facet, approximately 120 sq ft\n"
                    "  Method: Physical sample collection\n"
                    "  Estimated Turnaround: 24-48 hours (standard)\n"
                    "  itel NOW Available: Yes (30-minute field identification)\n\n"
                    "  Status: PENDING COLLECTION\n"
                    "  Note: Physical sample provides definitive material ID.\n"
                    "  DECISION SUPPORT ONLY — repair/replace determination\n"
                    "  requires licensed adjuster review."
                )),
                ("itel", (
                    "ITEL Material Sample Request Initiated.\n"
                    "  Request ID: ITEL-2026-02-11-00848\n"
                    "  Sample Type: Roof material identification\n"
                    "  Estimated Turnaround: 24-48 hours\n"
                    "  itel NOW mobile field ID available (30 min).\n\n"
                    "  Status: PENDING COLLECTION"
                )),
            ],
            ("submit_itel_analysis", "property_intel"): [
                ("analysis", (
                    "ITEL Material Analysis Complete.\n"
                    "  Analysis ID: ITEL-RPT-2026-00847\n"
                    "  Material Identified: CertainTeed Landmark Pro (Asphalt Shingle)\n"
                    "  Manufacturer: CertainTeed (Saint-Gobain)\n"
                    "  Year of Manufacture: 2017 (batch confirmed)\n"
                    "  Expected Lifespan: 30 years (manufacturer warranty)\n"
                    "  Current Age: 8 years\n"
                    "  Remaining Life: ~22 years\n\n"
                    "  Repair vs. Replace Analysis:\n"
                    "    Repair Cost (affected area): $2,840\n"
                    "    Full Replacement Cost: $18,200\n"
                    "    ITEL Recommendation: REPAIR (localized damage, 73% life remaining)\n\n"
                    "  Xactimate Line Items: 3 items generated\n"
                    "    - Remove/replace shingles (120 sq ft): $1,680\n"
                    "    - Underlayment replacement: $420\n"
                    "    - Flashing repair: $740\n\n"
                    "  DECISION SUPPORT ONLY — Final repair/replace determination\n"
                    "  requires licensed adjuster authorization.\n"
                    "  Human Override Tracking: Active"
                )),
                ("cost", (
                    "ITEL Cost Analysis Complete.\n"
                    "  Repair Estimate: $3,200\n"
                    "  Replacement Estimate: $22,500\n"
                    "  ITEL Recommendation: REPAIR\n"
                    "  Xactimate integration: Line items exported.\n\n"
                    "  DECISION SUPPORT ONLY."
                )),
            ],
        }

    def _generic_output(self, tool_name: str, user_request: str) -> str:
        """Generate a generic mock output when no specific match is found."""
        generic_outputs = {
            "sql_db_query": (
                "Query executed successfully.\n"
                "Results: 0 rows returned.\n"
                "Execution time: 12ms"
            ),
            "sql_db_schema": (
                "Schema retrieved.\n"
                "Table contains 6 columns and approximately 1,000 rows."
            ),
            "sql_db_list_tables": (
                "Found 8 tables in the database.\n"
                "Use sql_db_schema for detailed column information."
            ),
            "sql_db_query_checker": (
                "Query validation: VALID\n"
                "No syntax errors detected."
            ),
            "web_search": (
                "Search completed.\n"
                "Found 8 results matching your query.\n"
                "Top result relevance: High"
            ),
            "wikipedia": (
                "Wikipedia article found.\n"
                "Article length: Medium\n"
                "Last updated: 2025-12"
            ),
            "calculator": (
                "Calculation complete.\n"
                "Result computed successfully."
            ),
            "summarize": (
                "Summary generated.\n"
                "Key points extracted from provided text."
            ),
            "lookup_order": (
                "Order lookup complete.\n"
                "Please provide a valid order number for detailed results."
            ),
            "process_refund": (
                "Refund assessment initiated.\n"
                "Please provide the order number and reason for refund."
            ),
            "escalate_to_human": (
                "Escalation initiated.\n"
                "A human agent will be with you shortly."
            ),
            "search_faq": (
                "FAQ search complete.\n"
                "Found 3 articles matching your query."
            ),
            "property_lookup": (
                "Property lookup complete.\n"
                "Please provide a street address for detailed parcel results."
            ),
            "aerial_image_retrieve": (
                "Aerial imagery retrieved.\n"
                "Vertical and oblique views available.\n"
                "AI detections overlaid on imagery."
            ),
            "roof_condition_score": (
                "Roof condition assessment complete.\n"
                "RSI score computed with confidence metric."
            ),
            "peril_risk_score": (
                "Peril risk assessment complete.\n"
                "Hail, wind, and wildfire scores computed."
            ),
            "generate_property_report": (
                "Property intelligence report generated.\n"
                "Report includes AI detections, RSI score, and peril scores.\n"
                "DECISION SUPPORT ONLY."
            ),
            "request_material_sample": (
                "ITEL material sample request initiated.\n"
                "Please provide property address and damage area details.\n"
                "Status: PENDING"
            ),
            "submit_itel_analysis": (
                "ITEL analysis submission received.\n"
                "Material identification and cost analysis in progress.\n"
                "DECISION SUPPORT ONLY."
            ),
            "lookup_service": (
                "Service lookup complete.\n"
                "Please provide a service name or category for detailed results."
            ),
            "check_eligibility": (
                "Eligibility screening complete.\n"
                "Please specify the program you are interested in.\n"
                "IMPORTANT: This is preliminary information only."
            ),
            "find_office_location": (
                "Office location found.\n"
                "See details for address, hours, and accessibility."
            ),
            "search_policy": (
                "Policy search complete.\n"
                "Found relevant municipal policy documents."
            ),
            "submit_service_request": (
                "Service request submitted.\n"
                "You will receive a confirmation with tracking details."
            ),
            "escalate_to_staff": (
                "Escalation initiated.\n"
                "A government staff member will follow up with you."
            ),
        }
        return generic_outputs.get(tool_name, f"Tool '{tool_name}' executed. No specific output available.")
