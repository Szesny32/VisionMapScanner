#include <iostream>
#include <opencv2/opencv.hpp>
#include <winsock2.h>
#include <vector>

#pragma comment(lib, "ws2_32.lib")

#define PORT 12345
#define HOST "127.0.0.1"
#define MAX_BUFFER_SIZE 65536


int receiveData(SOCKET& sock, char* buffer, int bufferSize, sockaddr_in& clientAddr) {
    int addrLen = sizeof(clientAddr);
    return recvfrom(sock, buffer, bufferSize, 0, (SOCKADDR*)&clientAddr, &addrLen);
}

int main() {

    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "WINSOCK initialization failed!" << std::endl;
        return -1;
    }

    SOCKET udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (udpSocket == INVALID_SOCKET) {
        std::cerr << "Socket creation failed!" << std::endl;
        WSACleanup();
        return -1;
    }

    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(PORT);
    serverAddr.sin_addr.s_addr = INADDR_ANY;

    if (bind(udpSocket, (SOCKADDR*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
        std::cerr << "Binding failed!" << std::endl;
        closesocket(udpSocket);
        WSACleanup();
        return -1;
    }

    std::cout << "Waiting for data on port " << PORT << "..." << std::endl;

    char* buffer = new char[MAX_BUFFER_SIZE];
    sockaddr_in clientAddr;

    while (true) {
        int bytesReceived = receiveData(udpSocket, buffer, MAX_BUFFER_SIZE, clientAddr);
        if (bytesReceived == SOCKET_ERROR) {
            std::cerr << "Data reception failed!" << std::endl;
            break;
        }
        //std::cerr << "Received " << bytesReceived << " bytes." << std::endl;

        if (bytesReceived < 8) {
            std::cerr << "Invalid packet size!" << std::endl;
            continue;
        }

        int cam1ImageLength = *reinterpret_cast<int*>(buffer); 
        int cam2ImageLength = *reinterpret_cast<int*>(buffer + 4);

        //std::cerr << "CAM1 image length: " << cam1ImageLength << std::endl;
       // std::cerr << "CAM2 image length: " << cam2ImageLength << std::endl;

        if (bytesReceived < 8 + cam1ImageLength + cam2ImageLength) {
            std::cerr << "Incomplete image data!" << std::endl;
            continue;
        }

        char* buffer1 = new char[cam1ImageLength];
        char* buffer2 = new char[cam2ImageLength];
        std::memcpy(buffer1, buffer + 8, cam1ImageLength);
        std::memcpy(buffer2, buffer + 8 + cam1ImageLength, cam2ImageLength);


        cv::Mat cam1InputMat(1, cam1ImageLength, CV_8UC1, buffer1);
        cv::Mat cam2InputMat(1, cam2ImageLength, CV_8UC1, buffer2);

        cv::Mat cam1Image = cv::imdecode(cam1InputMat, cv::IMREAD_COLOR);
        cv::Mat cam2Image = cv::imdecode(cam2InputMat, cv::IMREAD_COLOR);

        delete[] buffer1;
        delete[] buffer2;

        if (cam1Image.empty() || cam2Image.empty()) {
            std::string log = "";
            if (cam1Image.empty()) log += ": CAM1 :";
            if (cam2Image.empty()) log += ": CAM2 :";
            std::cerr << "Failed to decode images!\n" << log << std::endl;
            continue;
        }

        cv::resize(cam1Image, cam1Image, cv::Size(108, 72));
        cv::resize(cam2Image, cam2Image, cv::Size(108, 72));

        cv::Mat combinedImage;
        cv::hconcat(cam1Image, cam2Image, combinedImage);

        cv::imshow("Stereovision", combinedImage);

        if (cv::waitKey(1) == 27) {
            break;
        }
    }

    delete[] buffer;
    closesocket(udpSocket);
    WSACleanup();
    return 0;
}