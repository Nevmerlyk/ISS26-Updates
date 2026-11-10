// Read-only search for UTF16/strided/XOR/additive name encodings in PS1 game data.
// Candidate hits are NOT evidence that a renderer uses these bytes.
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <array>
#include <cstdint>
#include <algorithm>
int main(int argc,char**argv){
 if(argc!=2){std::cerr<<"Usage: scan original-track01.bin\n";return 2;}
 std::ifstream file(argv[1],std::ios::binary);
 if(!file){std::cerr<<"File not found\n";return 2;}
 constexpr size_t LIMIT=48*1024*1024;
 std::vector<uint8_t> buf(LIMIT);
 file.read(reinterpret_cast<char*>(buf.data()),buf.size());
 buf.resize(file.gcount());
 const std::vector<std::string> tokens={"Russia","Greece","Jamaica","Ukraine","Turkey","Brazil","RUSSIA","GREECE","JAMAICA","UKRAINE"};
 size_t total=0;
 for(const auto& token:tokens){
  for(int stride:{1,2,4})for(int mode:{0,1,2}){
   // mode 0: plain ASCII, mode 1: same XOR mask for every character,
   // mode 2: same additive byte delta for every character.
   size_t count=0;
   for(size_t p=0;p+(token.size()-1)*stride<buf.size();++p){
    uint8_t key=(mode==0?0:mode==1?(buf[p]^uint8_t(token[0])):(uint8_t)(buf[p]-uint8_t(token[0])));
    if(mode==0 && buf[p]!=uint8_t(token[0]))continue;
    if((mode==1?(buf[p+stride]^key):mode==2?uint8_t(buf[p+stride]-key):buf[p+stride])!=uint8_t(token[1]))continue;
    if((mode==1?(buf[p+2*stride]^key):mode==2?uint8_t(buf[p+2*stride]-key):buf[p+2*stride])!=uint8_t(token[2]))continue;
    bool valid=true;
    for(size_t j=3;j<token.size();++j){
     uint8_t ch=mode==1?(buf[p+j*stride]^key):mode==2?uint8_t(buf[p+j*stride]-key):buf[p+j*stride];
     if(ch!=uint8_t(token[j])){valid=false;break;}
    }
    if(valid){++count;++total;if(count<=25)std::cout<<token<<","<<stride<<","<<mode<<","<<p<<","<<int(key)<<"\n";}
   }
   std::cerr<<"scanned "<<token<<" stride="<<stride<<" codec="<<mode<<" matched="<<count<<"\n";
  }
 }
 std::cerr<<"TOTAL="<<total<<"\n";
}
