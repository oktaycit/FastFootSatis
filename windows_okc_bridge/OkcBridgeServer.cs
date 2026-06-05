using IntegrationHub;
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Web.Script.Serialization;

namespace FastFootOkcBridge
{
    internal static class OkcBridgeServer
    {
        private const int DefaultPort = 8787;
        private const int SaleTimeoutSeconds = 120;

        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        private static readonly ConcurrentDictionary<string, PendingSale> PendingSales =
            new ConcurrentDictionary<string, PendingSale>();
        private static readonly POSCommunication Communication =
            POSCommunication.getInstance("FastFootSatis");
        private static readonly object FiscalInfoLock = new object();

        private static volatile bool _deviceConnected;
        private static volatile bool _fiscalInfoLoaded;
        private static string _lastDeviceId = "";
        private static string _lastFiscalInfo = "";

        private sealed class PendingSale
        {
            private readonly ManualResetEventSlim _done = new ManualResetEventSlim(false);

            public PendingSale()
            {
                Status = -1;
                Message = "";
                RawSaleInfo = "";
            }

            public string BasketId { get; set; }
            public ManualResetEventSlim Done { get { return _done; } }
            public bool Success { get; set; }
            public int Status { get; set; }
            public string Message { get; set; }
            public int ReceiptNo { get; set; }
            public int ZNo { get; set; }
            public string RawSaleInfo { get; set; }
        }

        [STAThread]
        private static void Main(string[] args)
        {
            var port = GetPort(args);
            var prefix = string.Format("http://+:{0}/", port);

            Communication.setDeviceStateCallback(DeviceStateCallback);
            Communication.setSerialInCallback(SerialInCallback);

            var listener = new HttpListener();
            listener.Prefixes.Add(prefix);
            listener.Start();

            Console.WriteLine(string.Format("FastFood OKC Bridge dinliyor: {0}", prefix));
            Console.WriteLine("Endpointler: GET /health, POST /api/sale, GET /api/fiscal-info");
            Console.WriteLine("Cikis icin Ctrl+C.");

            var listenerThread = new Thread(delegate() { ListenForRequests(listener); });
            listenerThread.IsBackground = true;
            listenerThread.Start();

            while (true)
            {
                Application.DoEvents();
                Thread.Sleep(50);
            }
        }

        private static void ListenForRequests(HttpListener listener)
        {
            while (true)
            {
                try
                {
                    var context = listener.GetContext();
                    ThreadPool.QueueUserWorkItem(delegate { HandleRequest(context); });
                }
                catch (Exception ex)
                {
                    Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} HTTP listener error: {1}", DateTime.Now, ex.Message));
                    Thread.Sleep(1000);
                }
            }
        }

        private static int GetPort(string[] args)
        {
            int fromArgs;
            if (args.Length > 0 && int.TryParse(args[0], out fromArgs))
            {
                return fromArgs;
            }

            var fromEnv = Environment.GetEnvironmentVariable("OKC_BRIDGE_PORT");
            int port;
            if (int.TryParse(fromEnv, out port))
            {
                return port;
            }

            return DefaultPort;
        }

        private static void DeviceStateCallback(bool isConnected, string id)
        {
            _deviceConnected = isConnected;
            _lastDeviceId = id ?? "";
            if (!isConnected)
            {
                _fiscalInfoLoaded = false;
                _lastFiscalInfo = "";
            }
            Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} OKC device state: {1} {2}", DateTime.Now, isConnected, id));
        }

        private static void SerialInCallback(int type, string value)
        {
            Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} OKC callback type={1}", DateTime.Now, type));

            if (type == 3)
            {
                CompletePendingSale(value);
            }
        }

        private static void CompletePendingSale(string saleInfoJson)
        {
            var saleInfo = DeserializeObject(saleInfoJson);
            var basketId = GetString(saleInfo, "basketID");

            PendingSale pending = null;
            if (!string.IsNullOrWhiteSpace(basketId))
            {
                PendingSales.TryRemove(basketId, out pending);
            }
            else if (PendingSales.Count == 1)
            {
                var first = PendingSales.First();
                PendingSales.TryRemove(first.Key, out pending);
            }

            if (pending == null)
            {
                Console.WriteLine("Eslesen bekleyen satis bulunamadi.");
                return;
            }

            pending.RawSaleInfo = saleInfoJson;
            pending.Status = GetInt(saleInfo, "status", -1);
            pending.Success = pending.Status == 0;
            pending.Message = GetString(saleInfo, "message");
            pending.ReceiptNo = GetInt(saleInfo, "receiptNo", 0);
            pending.ZNo = GetInt(saleInfo, "zNo", 0);
            pending.Done.Set();
        }

        private static void HandleRequest(HttpListenerContext context)
        {
            try
            {
                var path = context.Request.Url.AbsolutePath.TrimEnd('/').ToLowerInvariant();

                if (context.Request.HttpMethod == "GET" && path == "/health")
                {
                    WriteJson(context, new Dictionary<string, object>
                    {
                        { "success", true },
                        { "deviceConnected", _deviceConnected },
                        { "deviceId", _lastDeviceId },
                        { "pendingSales", PendingSales.Count }
                    });
                    return;
                }

                if (context.Request.HttpMethod == "GET" && path == "/api/fiscal-info")
                {
                    WriteJson(context, new Dictionary<string, object>
                    {
                        { "success", true },
                        { "deviceConnected", _deviceConnected },
                        { "fiscalInfo", _lastFiscalInfo },
                        { "message", "Live fiscalInfo sorgusu kapali; POS DLL bu cagriyi bazi kurulumlarda sonlandirabiliyor." }
                    });
                    return;
                }

                if (context.Request.HttpMethod == "POST" && path == "/api/sale")
                {
                    HandleSale(context);
                    return;
                }

                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "Endpoint bulunamadi" }
                }, 404);
            }
            catch (Exception ex)
            {
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", ex.Message }
                }, 500);
            }
        }

        private static void HandleSale(HttpListenerContext context)
        {
            var body = ReadBody(context.Request);
            if (string.IsNullOrWhiteSpace(body))
            {
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "Bos sepet istegi" }
                }, 400);
                return;
            }

            var basket = DeserializeObject(body);
            var basketId = GetString(basket, "basketID");
            if (string.IsNullOrWhiteSpace(basketId))
            {
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "basketID zorunlu" }
                }, 400);
                return;
            }

            var pending = new PendingSale { BasketId = basketId };
            PendingSales[basketId] = pending;

            var sendStatus = Communication.sendBasket(body);
            if (sendStatus != 1)
            {
                PendingSale removed;
                PendingSales.TryRemove(basketId, out removed);
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "IntegrationHub sendBasket basarisiz dondu" },
                    { "sendStatus", sendStatus },
                    { "deviceConnected", _deviceConnected }
                }, 502);
                return;
            }

            if (!pending.Done.Wait(TimeSpan.FromSeconds(SaleTimeoutSeconds)))
            {
                PendingSale removed;
                PendingSales.TryRemove(basketId, out removed);
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "OKC satis callback zaman asimi" },
                    { "deviceConnected", _deviceConnected }
                }, 504);
                return;
            }

            WriteJson(context, new Dictionary<string, object>
            {
                { "success", pending.Success },
                { "status", pending.Status },
                { "message", string.IsNullOrWhiteSpace(pending.Message) ? "OK" : pending.Message },
                { "receiptNo", pending.ReceiptNo },
                { "zNo", pending.ZNo },
                { "basketID", pending.BasketId },
                { "rawSaleInfo", pending.RawSaleInfo }
            }, pending.Success ? 200 : 502);
        }

        private static string GetFiscalInfo()
        {
            lock (FiscalInfoLock)
            {
                if (_fiscalInfoLoaded && !string.IsNullOrWhiteSpace(_lastFiscalInfo))
                {
                    return _lastFiscalInfo;
                }

                _lastFiscalInfo = Communication.getFiscalInfo();
                _fiscalInfoLoaded = !string.IsNullOrWhiteSpace(_lastFiscalInfo);
                return _lastFiscalInfo;
            }
        }

        private static string ReadBody(HttpListenerRequest request)
        {
            using (var reader = new StreamReader(request.InputStream, request.ContentEncoding ?? Encoding.UTF8))
            {
                return reader.ReadToEnd();
            }
        }

        private static Dictionary<string, object> DeserializeObject(string json)
        {
            return Json.Deserialize<Dictionary<string, object>>(json);
        }

        private static string GetString(IDictionary<string, object> data, string key)
        {
            object value;
            if (data == null || !data.TryGetValue(key, out value) || value == null)
            {
                return "";
            }

            return Convert.ToString(value);
        }

        private static int GetInt(IDictionary<string, object> data, string key, int fallback)
        {
            object value;
            if (data == null || !data.TryGetValue(key, out value) || value == null)
            {
                return fallback;
            }

            try
            {
                return Convert.ToInt32(value);
            }
            catch
            {
                return fallback;
            }
        }

        private static void WriteJson(HttpListenerContext context, object payload, int statusCode = 200)
        {
            var json = Json.Serialize(payload);
            var bytes = Encoding.UTF8.GetBytes(json);

            context.Response.StatusCode = statusCode;
            context.Response.ContentType = "application/json; charset=utf-8";
            context.Response.ContentLength64 = bytes.Length;
            context.Response.OutputStream.Write(bytes, 0, bytes.Length);
            context.Response.OutputStream.Close();
        }
    }
}
