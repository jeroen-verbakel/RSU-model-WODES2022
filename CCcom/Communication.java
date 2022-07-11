package CCcom;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.util.ArrayList;
import java.util.List;

public class Communication {
    static byte[] LOCALHOST = { 127, 0, 0, 1 };
    static int DESTINATIONPORT = 3000; // Port for sending, +1 for receiving.

    // CC send
    public static boolean send(int messageNumber, int messageType, List<Integer> data, int LEN) {
        byte[] message = new byte[LEN + 2];
        message[0] = (byte)(messageNumber % 256);
        message[1] = (byte)(messageType % 256);
        int i = 2;
        for (int d: data) {
            message[i] = (byte)(d % 256);
            i++;
        }
        try {
            DatagramSocket socket = new DatagramSocket();
            socket.connect(InetAddress.getByAddress(LOCALHOST), DESTINATIONPORT);
            DatagramPacket packet = new DatagramPacket(message, LEN + 2);
            socket.send(packet);
            socket.close();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // CC receive
    public static List<Integer> receive(double time, int LEN) {
        byte[] message = new byte[LEN + 3];
        try {
            DatagramSocket socket = new DatagramSocket();
            socket.connect(InetAddress.getByAddress(LOCALHOST), DESTINATIONPORT + 1);
            DatagramPacket packet = new DatagramPacket(message, message.length);
            socket.send(packet);
            socket.receive(packet);
            socket.close();
            message = packet.getData();
        } catch (Exception e) {
        }
        ArrayList<Integer> returnValue = new ArrayList<Integer>();
        for (int i = 0; i < message.length; i++) {
            returnValue.add((int)((256 + message[i]) % 256));
        }
        return returnValue;
    }

    static int RSUPORT = 5000; // Port for sending, +1 for receiving.

    // RSU send
    public static boolean send2(int messageNumber, int messageType, List<Integer> data, List<Integer> acks, int LEN) {
        int len = 2 + LEN + acks.size();
        byte[] message = new byte[len];
        message[0] = (byte)(messageNumber % 256);
        message[1] = (byte)(messageType % 256);
        int i = 2;
        for (int d: data) {
            message[i] = (byte)(d % 256);
            i++;
        }
        for (int a: acks) {
            message[i] = (byte)a;
            i++;
        }
        try {
            DatagramSocket socket = new DatagramSocket();
            socket.connect(InetAddress.getByAddress(LOCALHOST), RSUPORT);
            DatagramPacket packet = new DatagramPacket(message, len);
            socket.send(packet);
            socket.close();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // RSU receive
    public static List<Integer> receive2(double time, int LEN) {
        byte[] message = new byte[4 + LEN + 15];
        try {
            DatagramSocket socket = new DatagramSocket();
            socket.connect(InetAddress.getByAddress(LOCALHOST), RSUPORT + 1);
            DatagramPacket packet = new DatagramPacket(message, message.length);
            socket.send(packet);
            socket.receive(packet);
            socket.close();
            message = packet.getData();
        } catch (Exception e) {
        }
        ArrayList<Integer> returnValue = new ArrayList<Integer>();
        for (int i = 0; i < message.length; i++) {
            returnValue.add((int)((256 + message[i]) % 256));
        }
        return returnValue;
    }
}
