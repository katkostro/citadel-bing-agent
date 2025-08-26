# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import os
import json
import logging
from typing import Dict, List, Any, Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

logger = logging.getLogger("azureaiapp")


class InternalKnowledgePlugin:
    """Plugin for accessing internal banking knowledge and customer data"""
    
    def __init__(self):
        self._customer_data = self._load_customer_data()
        self._product_data = self._load_product_data()
        self._policies = self._load_banking_policies()
    
    def _load_customer_data(self) -> Dict[str, Any]:
        """Load customer data from files directory"""
        customer_data = {}
        files_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'files')
        
        try:
            for filename in os.listdir(files_dir):
                if filename.startswith('customer_info_') and filename.endswith('.json'):
                    filepath = os.path.join(files_dir, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        customer_id = data.get('customer_id', filename)
                        customer_data[customer_id] = data
            logger.info(f"Loaded {len(customer_data)} customer records")
        except Exception as e:
            logger.error(f"Error loading customer data: {e}")
        
        return customer_data
    
    def _load_product_data(self) -> Dict[str, Any]:
        """Load product information from files directory"""
        product_data = {}
        files_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'files')
        
        try:
            for filename in os.listdir(files_dir):
                if filename.startswith('product_info_') and filename.endswith('.md'):
                    filepath = os.path.join(files_dir, filename)
                    with open(filepath, 'r') as f:
                        content = f.read()
                        product_id = filename.replace('product_info_', '').replace('.md', '')
                        product_data[product_id] = content
            logger.info(f"Loaded {len(product_data)} product documents")
        except Exception as e:
            logger.error(f"Error loading product data: {e}")
        
        return product_data
    
    def _load_banking_policies(self) -> Dict[str, str]:
        """Load internal banking policies and procedures"""
        return {
            "account_opening": "New accounts require ID verification, credit check, and minimum deposit of $100.",
            "loan_approval": "Loans require income verification, credit score above 650, and debt-to-income ratio below 40%.",
            "wire_transfer": "Wire transfers above $10,000 require manager approval and additional verification.",
            "fraud_protection": "Suspicious activities trigger automatic account holds and customer notifications.",
            "customer_service": "All customer inquiries should be handled within 24 hours with full documentation.",
            "compliance": "All transactions must comply with BSA, AML, and KYC requirements."
        }
    
    @kernel_function(
        description="Get customer account information and transaction history",
        name="get_customer_info"
    )
    def get_customer_info(self, customer_id: str = "") -> str:
        """Retrieve customer information by ID or return general customer service info"""
        if not customer_id:
            return "Please provide a customer ID to retrieve specific account information."
        
        if customer_id in self._customer_data:
            data = self._customer_data[customer_id]
            return f"""Customer Information:
Name: {data.get('name', 'N/A')}
Account Type: {data.get('account_type', 'N/A')}
Balance: {data.get('balance', 'N/A')}
Status: {data.get('status', 'N/A')}
Last Transaction: {data.get('last_transaction', 'N/A')}
Contact: {data.get('contact', 'N/A')}"""
        else:
            return f"Customer ID {customer_id} not found in our records."
    
    @kernel_function(
        description="Get information about banking products and services",
        name="get_product_info"
    )
    def get_product_info(self, product_type: str = "") -> str:
        """Get detailed information about banking products"""
        if not product_type:
            available_products = list(self._product_data.keys())
            return f"Available products: {', '.join(available_products)}. Please specify a product type."
        
        # Find matching product
        for product_id, content in self._product_data.items():
            if product_type.lower() in product_id.lower() or product_type.lower() in content.lower():
                return content
        
        return f"Product information for '{product_type}' not found. Available products: {', '.join(self._product_data.keys())}"
    
    @kernel_function(
        description="Get internal banking policies and procedures",
        name="get_banking_policy"
    )
    def get_banking_policy(self, policy_type: str = "") -> str:
        """Retrieve internal banking policies and procedures"""
        if not policy_type:
            available_policies = list(self._policies.keys())
            return f"Available policies: {', '.join(available_policies)}. Please specify a policy type."
        
        # Find matching policy
        for policy_key, policy_content in self._policies.items():
            if policy_type.lower() in policy_key.lower():
                return f"Policy for {policy_key}: {policy_content}"
        
        return f"Policy for '{policy_type}' not found. Available policies: {', '.join(self._policies.keys())}"
    
    @kernel_function(
        description="Search across all internal knowledge for relevant information",
        name="search_internal_knowledge"
    )
    def search_internal_knowledge(self, query: str) -> str:
        """Search across customer data, products, and policies for relevant information"""
        if not query:
            return "Please provide a search query."
        
        query_lower = query.lower().strip()
        
        # Handle greetings and general queries - don't return products
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
        simple_queries = ['help', 'start', 'begin', 'what can you do', 'how are you']
        
        if (any(query_lower == greeting for greeting in greetings) or 
            any(simple in query_lower for simple in simple_queries) or 
            len(query_lower.split()) <= 2 and any(greeting in query_lower for greeting in greetings)):
            return "Hello! I'm your outdoor gear assistant. I can help you find information about camping equipment, hiking gear, tents, sleeping bags, backpacks, and more. What specific products are you looking for?"
        
        results = []
        
        # Extract meaningful keywords (be much more selective)
        common_words = {'tell', 'me', 'about', 'what', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'among', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that', 'these', 'those', 'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might', 'must', 'do', 'does', 'did', 'have', 'has', 'had', 'be', 'am', 'is', 'are', 'was', 'were', 'been', 'being', 'show', 'find', 'list', 'get', 'give', 'looking', 'need', 'want', 'like', 'see', 'view'}
        keywords = [word for word in query_lower.split() if word not in common_words and len(word) > 2]
        
        # If no meaningful keywords, don't return everything
        if not keywords:
            return "Please be more specific about what camping or outdoor gear you're looking for. I can help with tents, sleeping bags, backpacks, hiking gear, camping stoves, and more."
        
        # Define product categories for more targeted searching
        product_categories = {
            'tent': ['tent', 'tents', 'shelter'],
            'table': ['table', 'tables', 'dining'],
            'chair': ['chair', 'chairs', 'seat'],
            'backpack': ['backpack', 'backpacks', 'pack', 'daypack'],
            'sleeping': ['sleeping', 'sleep'],
            'boots': ['boot', 'boots', 'shoe', 'shoes', 'footwear', 'sandal', 'sandals'],
            'jacket': ['jacket', 'jackets'],
            'stove': ['stove', 'stoves', 'cooking', 'cook', 'burner'],
            'pants': ['pant', 'pants'],
            'bag': ['bag', 'bags']
        }
        
        # Check if query is asking for specific product categories
        relevant_categories = []
        for category, category_keywords in product_categories.items():
            if any(cat_keyword in keywords for cat_keyword in category_keywords):
                relevant_categories.append(category)
        
        # Search policies only for policy-related queries
        policy_keywords = ['policy', 'rule', 'return', 'warranty', 'service', 'support']
        if any(policy_kw in keywords for policy_kw in policy_keywords):
            for policy_key, policy_content in self._policies.items():
                if any(keyword in policy_key.lower() or keyword in policy_content.lower() for keyword in keywords):
                    results.append(f"Policy - {policy_key}: {policy_content}")
        
        # Search products with much more targeted filtering
        product_matches = 0
        for product_id, content in self._product_data.items():
            content_lower = content.lower()
            should_include = False
            
            # Extract the Category field from the product content
            category_match = None
            for line in content.split('\n'):
                if line.strip().lower().startswith('## category'):
                    # Get the next line which should contain the category
                    lines = content.split('\n')
                    category_line_idx = lines.index(line)
                    if category_line_idx + 1 < len(lines):
                        category_match = lines[category_line_idx + 1].strip().lower()
                    break
            
            # If specific categories were requested, only match those categories EXACTLY
            if relevant_categories:
                if category_match:
                    for category in relevant_categories:
                        category_keywords = product_categories[category]
                        # Check if the product's category matches any of the requested category keywords
                        if any(cat_keyword in category_match for cat_keyword in category_keywords):
                            should_include = True
                            break
            else:
                # For general searches without specific categories, require strong keyword matches in product name/description
                # But NOT in random description text
                product_name = content.split('\n')[1] if len(content.split('\n')) > 1 else ""
                product_name_lower = product_name.lower()
                
                strong_keywords = [kw for kw in keywords if len(kw) > 3]
                if strong_keywords:
                    # Only match if keywords appear in product name or category, not random description
                    name_matches = sum(1 for kw in strong_keywords if kw in product_name_lower)
                    category_matches = sum(1 for kw in strong_keywords if category_match and kw in category_match)
                    
                    if name_matches >= 1 or category_matches >= 1:
                        should_include = True
            
            if should_include:
                results.append(f"Product - {product_id}: {content[:300]}...")
                product_matches += 1
                if product_matches >= 8:  # Reasonable limit
                    break
        
        # Search customer data only for customer-specific queries
        customer_keywords = ['customer', 'account', 'order', 'purchase']
        if any(cust_kw in keywords for cust_kw in customer_keywords):
            customer_matches = 0
            for customer_id, data in self._customer_data.items():
                if any(any(keyword in str(value).lower() for keyword in keywords) for value in data.values()):
                    customer_matches += 1
            
            if customer_matches > 0:
                results.append(f"Found {customer_matches} matching customer records (details require specific customer ID)")
        
        if results:
            return "\n\n".join(results)
        else:
            return f"No specific products found for '{query}'. I can help you find camping gear like tents, sleeping bags, backpacks, hiking boots, camping stoves, and outdoor clothing. What are you looking for?"
