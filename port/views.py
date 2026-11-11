import socket
import threading
import json
import csv
from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from .models import ScanHistory, PortResult

open_ports = []
lock = threading.Lock()

def get_banner(sock):
    try:
        sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
        return sock.recv(1024).decode(errors="ignore").strip()
    except:
        return ""

def scan_port(host, port, results_queue):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((host, port))
        if result == 0:
            service = "unknown"
            try:
                service = socket.getservbyport(port)
            except:
                pass
            banner = get_banner(sock)
            with lock:
                results_queue.append((port, service, banner[:60]))
                open_ports.append((port, service, banner[:60]))
        sock.close()
    except socket.error:
        pass

def scan_generator(host, start, end, threads=150):
    global open_ports
    open_ports = []
    results_queue = []
    thread_list = []

    for port in range(start, end + 1):
        t = threading.Thread(target=scan_port, args=(host, port, results_queue))
        thread_list.append(t)
        t.start()

        if len(thread_list) >= threads:
            for t in thread_list:
                t.join()
            for (p, svc, ban) in results_queue:
                yield f"data: {json.dumps({'type': 'open_port', 'port': p, 'service': svc, 'banner': ban})}\n\n"
            results_queue.clear()
            thread_list = []

    for t in thread_list:
        t.join()
    for (p, svc, ban) in results_queue:
        yield f"data: {json.dumps({'type': 'open_port', 'port': p, 'service': svc, 'banner': ban})}\n\n"

    # Save to database
    scan = ScanHistory.objects.create(
        target_ip=host,
        open_ports_count=len(open_ports)
    )
    for (p, svc, ban) in open_ports:
        PortResult.objects.create(
            scan=scan,
            port=p,
            service=svc,
            banner=ban
        )

    yield f"data: {json.dumps({'type': 'summary', 'count': len(open_ports), 'scan_id': scan.id})}\n\n"


def index(request):
    history = ScanHistory.objects.order_by('-scanned_at')[:10]
    return render(request, 'index.html', {'history': history})


def scan_view(request):
    host = request.GET.get('ip', '')
    if not host:
        return StreamingHttpResponse(
            f"data: {json.dumps({'type': 'error', 'message': 'No IP provided'})}\n\n",
            content_type='text/event-stream'
        )
    try:
        socket.setdefaulttimeout(3)
        socket.gethostbyname(host)
    except socket.gaierror:
        return StreamingHttpResponse(
            f"data: {json.dumps({'type': 'error', 'message': f'Host {host} is unreachable or invalid'})}\n\n",
            content_type='text/event-stream'
        )
    response = StreamingHttpResponse(
        scan_generator(host, 1, 1024),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    return response


def export_json(request, scan_id):
    try:
        scan = ScanHistory.objects.get(id=scan_id)
    except ScanHistory.DoesNotExist:
        return JsonResponse({'error': 'Scan not found'}, status=404)

    data = {
        'target_ip': scan.target_ip,
        'scanned_at': scan.scanned_at.strftime('%Y-%m-%d %H:%M:%S'),
        'open_ports_count': scan.open_ports_count,
        'results': [
            {'port': r.port, 'service': r.service, 'banner': r.banner}
            for r in scan.results.all()
        ]
    }
    response = HttpResponse(
        json.dumps(data, indent=4),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="scan_{scan_id}.json"'
    return response


def export_csv(request, scan_id):
    try:
        scan = ScanHistory.objects.get(id=scan_id)
    except ScanHistory.DoesNotExist:
        return HttpResponse('Scan not found', status=404)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="scan_{scan_id}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Port', 'Service', 'Banner'])
    for r in scan.results.all():
        writer.writerow([r.port, r.service, r.banner])

    return response