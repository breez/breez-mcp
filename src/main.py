import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Dict, Any, List

from fastmcp import FastMCP
from pydantic import Field

from .config import Config
from .sdk_manager import SDKManager

# Global SDK manager
sdk_manager = None

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage application lifecycle"""
    global sdk_manager
    logging.info("Starting Breez MCP server...")

    # Initialize SDK
    sdk_manager = SDKManager()
    await sdk_manager.connect()

    try:
        yield
    finally:
        if sdk_manager:
            await sdk_manager.disconnect()
            logging.info("Server shutdown complete")

# Create FastMCP server instance with lifecycle management
mcp = FastMCP("breez-mcp", lifespan=app_lifespan)

@mcp.tool()
async def get_balance() -> Dict[str, Any]:
    """Get wallet balance"""
    try:
        from breez_sdk_spark import GetInfoRequest
        info = await sdk_manager.get_sdk().get_info(request=GetInfoRequest(ensure_synced=True))

        # Build comprehensive JSON response
        balance = {
            "balance_sat": getattr(info, 'balance_sats', 0) if hasattr(info, 'balance_sats') else 0,
            "pending_incoming_sat": getattr(info, 'pending_incoming_sats', 0) if hasattr(info, 'pending_incoming_sats') else 0,
            "pending_outgoing_sat": getattr(info, 'pending_outgoing_sats', 0) if hasattr(info, 'pending_outgoing_sats') else 0,
        }

        # Add additional balance information if available
        if hasattr(info, 'max_payable_sats'):
            balance["max_payable_sat"] = info.max_payable_sats
        if hasattr(info, 'max_receivable_sats'):
            balance["max_receivable_sat"] = info.max_receivable_sats
        if hasattr(info, 'total_fees_paid_sats'):
            balance["total_fees_paid_sat"] = info.total_fees_paid_sats

        # Add human-readable formatting
        balance["balance_formatted"] = f"{balance['balance_sat']:,} sats"
        if balance["pending_incoming_sat"] > 0:
            balance["pending_incoming_formatted"] = f"{balance['pending_incoming_sat']:,} sats"
        if balance["pending_outgoing_sat"] > 0:
            balance["pending_outgoing_formatted"] = f"{balance['pending_outgoing_sat']:,} sats"

        return balance
    except Exception as e:
        logging.error(f"Error getting balance: {e}")
        return {
            "error": "Failed to get balance",
            "details": str(e)
        }

@mcp.tool()
async def get_node_info() -> Dict[str, Any]:
    """Get node information"""
    try:
        from breez_sdk_spark import GetInfoRequest
        info = await sdk_manager.get_sdk().get_info(request=GetInfoRequest(ensure_synced=True))

        # Build comprehensive JSON response with consistent structure
        node_info = {}

        # Try different possible attribute names for node ID
        node_id = None
        for attr in ['id', 'node_id', 'nodeId', 'pubkey', 'public_key', 'node_pubkey']:
            if hasattr(info, attr):
                node_id = getattr(info, attr)
                break

        node_info["node_id"] = node_id
        node_info["network"] = str(getattr(info, 'network', 'unknown')) if hasattr(info, 'network') else 'unknown'

        # Handle channels and connectivity
        channels_count = 0
        if hasattr(info, 'channels') and info.channels:
            channels_count = len(info.channels)
        node_info["channels_count"] = channels_count
        node_info["channels"] = channels_count > 0

        # Include balance information
        if hasattr(info, 'balance_sats'):
            node_info["balance_sat"] = info.balance_sats
            node_info["balance_formatted"] = f"{info.balance_sats:,} sats"

        # Include pending balances
        if hasattr(info, 'pending_incoming_sats'):
            node_info["pending_incoming_sat"] = info.pending_incoming_sats
        if hasattr(info, 'pending_outgoing_sats'):
            node_info["pending_outgoing_sat"] = info.pending_outgoing_sats

        # Include sync status
        if hasattr(info, 'synced'):
            node_info["synced"] = info.synced
        else:
            node_info["synced"] = True  # Assume synced if we got info

        # Include block height if available
        if hasattr(info, 'block_height'):
            node_info["block_height"] = info.block_height

        # Add capabilities and limits if available
        capabilities = {}
        if hasattr(info, 'max_payable_sats'):
            capabilities["max_payable_sat"] = info.max_payable_sats
        if hasattr(info, 'max_receivable_sats'):
            capabilities["max_receivable_sat"] = info.max_receivable_sats

        if capabilities:
            node_info["capabilities"] = capabilities

        return node_info
    except Exception as e:
        logging.error(f"Error getting node info: {e}")
        return {
            "error": "Failed to get node info",
            "details": str(e)
        }

@mcp.tool()
async def send_payment(
    invoice: Annotated[str, Field(description="BOLT11 invoice to pay")]
) -> Dict[str, Any]:
    """Send a Lightning payment"""
    try:
        from breez_sdk_spark import PrepareSendPaymentRequest, SendPaymentRequest

        sdk = sdk_manager.get_sdk()

        # Prepare payment
        prepare_request = PrepareSendPaymentRequest(payment_request=invoice)
        prepare_response = await sdk.prepare_send_payment(request=prepare_request)

        # Send payment
        send_request = SendPaymentRequest(prepare_response=prepare_response)
        send_response = await sdk.send_payment(request=send_request)

        # Build JSON response
        payment_result = {
            "status": "success",
            "message": "Payment sent successfully"
        }

        # Extract payment information using improved pattern
        if hasattr(send_response, 'payment') and send_response.payment:
            payment = send_response.payment

            # Create payment data structure
            payment_data = {
                'id': getattr(payment, 'id', None),
                'timestamp': getattr(payment, 'timestamp', None),
                'amount_sat': getattr(payment, 'amount', None),
                'fees_sat': getattr(payment, 'fees', None),
                'payment_type': str(getattr(payment, 'payment_type', 'UNKNOWN')),
                'status': str(getattr(payment, 'status', 'UNKNOWN')),
                'destination': getattr(payment, 'destination', None),
                'tx_id': getattr(payment, 'tx_id', None),
            }

            # Extract details from payment.details if available
            if hasattr(payment, 'details') and payment.details:
                details = payment.details
                if hasattr(details, 'payment_hash'):
                    payment_data['payment_hash'] = details.payment_hash
                if hasattr(details, 'preimage'):
                    payment_data['preimage'] = details.preimage
                if hasattr(details, 'description'):
                    payment_data['description'] = details.description

            # Add payment data to result
            payment_result.update(payment_data)

            # Add human-readable status
            if payment_data['status'] == 'PaymentStatus.PENDING':
                payment_result["payment_status"] = "pending"
            elif payment_data['status'] == 'PaymentStatus.COMPLETED':
                payment_result["payment_status"] = "completed"
            elif payment_data['status'] == 'PaymentStatus.FAILED':
                payment_result["payment_status"] = "failed"
            else:
                payment_result["payment_status"] = payment_data['status']

        # Also check response for direct attributes
        if hasattr(send_response, 'payment_hash'):
            payment_result["txid"] = send_response.payment_hash

        return payment_result
    except Exception as e:
        logging.error(f"Error sending payment: {e}")
        return {
            "status": "error",
            "message": "Failed to send payment",
            "details": str(e)
        }

@mcp.tool()
async def create_invoice(
    amount_sats: Annotated[int, Field(description="Amount in satoshis", ge=1)],
    description: Annotated[str, Field(description="Payment description")] = "MCP Payment"
) -> Dict[str, Any]:
    """Create a Lightning invoice"""
    try:
        from breez_sdk_spark import ReceivePaymentRequest, ReceivePaymentMethod

        sdk = sdk_manager.get_sdk()

        # Create invoice
        payment_method = ReceivePaymentMethod.BOLT11_INVOICE(
            description=description,
            amount_sats=amount_sats
        )
        request = ReceivePaymentRequest(payment_method=payment_method)
        response = await sdk.receive_payment(request=request)

        # Build JSON response with improved structure
        invoice_result = {
            "status": "success",
            "message": "Invoice created successfully",
            "amount_sat": amount_sats,
            "description": description
        }

        # Extract invoice information using improved pattern
        if hasattr(response, 'payment_request'):
            invoice_result["invoice"] = response.payment_request
            invoice_result["destination"] = response.payment_request

        if hasattr(response, 'fee_sats'):
            invoice_result["fee_sat"] = response.fee_sats

        # Check for LNURL pay request if available
        if hasattr(response, 'lnurl_pay_request'):
            invoice_result["lnurl"] = response.lnurl_pay_request

        # Extract additional details if available
        invoice_details = {}
        if hasattr(response, 'payment_hash'):
            invoice_details["payment_hash"] = response.payment_hash
            invoice_result["payment_hash"] = response.payment_hash

        if hasattr(response, 'preimage'):
            invoice_details["preimage"] = response.preimage
            invoice_result["preimage"] = response.preimage

        if hasattr(response, 'expiry'):
            invoice_details["expiry"] = response.expiry
            invoice_result["expiry"] = response.expiry

        # Add details object if we have any
        if invoice_details:
            invoice_result["details"] = invoice_details

        return invoice_result
    except Exception as e:
        logging.error(f"Error creating invoice: {e}")
        return {
            "status": "error",
            "message": "Failed to create invoice",
            "details": str(e)
        }

@mcp.tool()
async def list_payments(
    limit: Annotated[int, Field(description="Number of payments to return", ge=1, le=100)] = 10
) -> Dict[str, Any]:
    """List recent payments"""
    try:
        from breez_sdk_spark import ListPaymentsRequest

        sdk = sdk_manager.get_sdk()
        request = ListPaymentsRequest(limit=limit, sort_ascending=False)
        response = await sdk.list_payments(request=request)

        # Build JSON response
        result = {
            "payments": [],
            "total_count": 0
        }

        if not hasattr(response, 'payments') or not response.payments:
            return result

        result["total_count"] = len(response.payments)

        # Extract payment information using the improved pattern from CLI
        for payment in response.payments:
            # Create payment dictionary following the SDK example pattern
            payment_data = {
                'id': getattr(payment, 'id', None),
                'timestamp': getattr(payment, 'timestamp', None),
                'amount_sat': getattr(payment, 'amount', None),
                'fees_sat': getattr(payment, 'fees', None),
                'payment_type': str(getattr(payment, 'payment_type', 'UNKNOWN')),
                'status': str(getattr(payment, 'status', 'UNKNOWN')),
                'details': {},
                'destination': getattr(payment, 'destination', None),
                'tx_id': getattr(payment, 'tx_id', None),
            }

            # Extract details from payment.details if available
            if hasattr(payment, 'details') and payment.details:
                details = payment.details
                payment_data['details'] = {
                    'description': getattr(details, 'description', None),
                    'preimage': getattr(details, 'preimage', None),
                    'invoice': getattr(details, 'invoice', None),
                    'payment_hash': getattr(details, 'payment_hash', None),
                    'destination_pubkey': getattr(details, 'destination_pubkey', None),
                    'lnurl_pay_info': getattr(details, 'lnurl_pay_info', None),
                    'lnurl_withdraw_info': getattr(details, 'lnurl_withdraw_info', None),
                }

                # Also include key fields at top level for easier access
                if hasattr(details, 'payment_hash'):
                    payment_data['payment_hash'] = details.payment_hash
                if hasattr(details, 'description'):
                    payment_data['description'] = details.description
                if hasattr(details, 'preimage'):
                    payment_data['preimage'] = details.preimage
                if hasattr(details, 'destination_pubkey'):
                    payment_data['destination_pubkey'] = details.destination_pubkey

            # Add human-readable type and status at top level
            if payment_data['payment_type'] == 'PaymentType.SEND':
                payment_data['type'] = 'sent'
            elif payment_data['payment_type'] == 'PaymentType.RECEIVE':
                payment_data['type'] = 'received'
            else:
                payment_data['type'] = payment_data['payment_type']

            result["payments"].append(payment_data)

        return result
    except Exception as e:
        logging.error(f"Error listing payments: {e}")
        return {
            "error": "Failed to list payments",
            "details": str(e)
        }

# Health check endpoint for HTTP mode
@mcp.custom_route("/health", methods=["GET"])
async def health_check():
    """Health check endpoint"""
    try:
        if sdk_manager and sdk_manager.get_sdk():
            return {
                "status": "healthy",
                "sdk_connected": True,
                "network": os.getenv("BREEZ_NETWORK", "mainnet")
            }
        else:
            return {
                "status": "unhealthy",
                "sdk_connected": False,
                "error": "SDK not connected"
            }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

def main():
    """Main entry point that supports both stdio and HTTP modes"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    # Check transport mode from environment
    transport_mode = os.getenv("BREEZ_TRANSPORT_MODE", "stdio").lower()

    if transport_mode == "http":
        # HTTP mode
        host = os.getenv("BREEZ_HTTP_HOST", "0.0.0.0")
        port = int(os.getenv("BREEZ_HTTP_PORT", "8000"))
        path = os.getenv("BREEZ_HTTP_PATH", "/mcp")

        logging.info(f"Starting Breez MCP server in HTTP mode on {host}:{port}{path}")

        # Add CORS middleware for browser-based clients if needed
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Configure appropriately for production
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=[
                    "mcp-protocol-version",
                    "mcp-session-id",
                    "Authorization",
                    "Content-Type",
                ],
                expose_headers=["mcp-session-id"],
            )
        ]

        # Create ASGI app with middleware
        app = mcp.http_app(path=path, middleware=middleware)

        # Run with uvicorn
        import uvicorn
        uvicorn.run(app, host=host, port=port)

    elif transport_mode == "asgi":
        # ASGI mode - return the app for external ASGI server
        path = os.getenv("BREEZ_HTTP_PATH", "/mcp")
        app = mcp.http_app(path=path)
        print(f"ASGI app created at path: {path}")
        print("Run with: uvicorn main:app --host 0.0.0.0 --port 8000")

    else:
        # Default: STDIO mode
        logging.info("Starting Breez MCP server in STDIO mode")
        mcp.run()

if __name__ == "__main__":
    main()
